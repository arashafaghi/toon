"""Textual application host and console entry point.

The host owns the ``App``, the overall layout, and the REPL lifetime. It
implements :class:`toon.api.ViewHost` so commands (built-in or plugin) can
navigate to registered UI contributions without touching app internals.

Startup order is deliberate: built-in commands are registered *first* so a
plugin can never shadow ``help``/``clear``/``plugins``; then local plugins are
discovered under ``plugins/`` and loaded, with per-plugin failures reported in
the REPL. Layout (base screen): header on top, a persistent content area, the
REPL, and a footer that lists the visible key bindings.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import cast

from textual.app import App, ComposeResult
from textual.binding import Binding

from toon.api import logger
from toon.runtime.builtins import register_builtins
from toon.runtime.dispatcher import Dispatcher
from toon.runtime.plugin_loader import LoadReport, load_plugins
from toon.runtime.registry import Registry
from toon.runtime.state import AppState, StateStore
from toon.ui.content import ContentArea
from toon.ui.footer import AppFooter
from toon.ui.header import AppHeader
from toon.ui.logging import install_logging
from toon.ui.palette import CommandProvider, PaletteSystemCommands, build_commands
from toon.ui.repl import Repl

_PLUGINS_ENV = "TOON_PLUGINS_DIR"


def _plugins_dir() -> Path:
    """Return the directory scanned for plugins (``./plugins`` by default)."""
    override = os.environ.get(_PLUGINS_ENV)
    return Path(override) if override else Path.cwd() / "plugins"


class ToonApp(PaletteSystemCommands, App[None]):
    """Interactive REPL host with local plugin support."""

    # Load styles from the external file
    CSS_PATH = "style.tcss"

    TITLE = "Toon"

    # Bindings with ``show=True`` appear in the footer automatically; the
    # command-palette hint is added by the footer as well.
    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", show=True),
        Binding("ctrl+w", "close_view", "Close view", show=True, priority=True),
        Binding("escape", "pop_view", "Back", show=False),
    ]

    # Command palette contents live in toon.ui.palette.
    COMMANDS = cast("set[CommandProvider]", build_commands())

    def __init__(
        self,
        *,
        plugins_dir: Path | None = None,
        state_path: Path | None = None,
    ) -> None:
        super().__init__()
        # Route Loguru into the REPL before anything (including plugins) logs.
        self.log_sink = install_logging(self)
        self.registry = Registry()
        # Built-ins first, so plugins cannot shadow them.
        self.load_report = LoadReport(())
        register_builtins(self.registry, plugins=lambda: self.load_report.summaries())
        self.load_report = load_plugins(plugins_dir or _plugins_dir(), self.registry)
        self.dispatcher = Dispatcher(self.registry)
        # Remember/reload the open views; creates an empty file if absent.
        self.state_store = StateStore(state_path)
        self.state: AppState = self.state_store.load()

    def compose(self) -> ComposeResult:
        yield AppHeader(id="header")
        yield ContentArea(id="content")
        yield Repl(
            self.dispatcher,
            self,
            history=self.state.history,
            on_history_changed=self._save_history,
            id="repl",
        )
        yield AppFooter(id="footer")

    def on_mount(self) -> None:
        """Report the plugin load summary once the REPL is on screen."""
        repl = self.query_one(Repl)
        # Flush log records buffered during startup (e.g. plugin loading).
        self.log_sink.attach(repl)
        loaded = self.load_report.loaded_names
        if loaded:
            repl.write_output(f"Loaded {len(loaded)} plugin(s): {', '.join(loaded)}")
        for failure in self.load_report.failures:
            repl.write_output(f"[red]Plugin '{failure.name}' failed to load: {failure.error}[/red]")
        if not loaded and not self.load_report.failures:
            repl.write_output("No plugins found. Type 'help' for available commands.")
        # Bars start with only session-wide items (no views open yet).
        self._sync_bars()
        # Reopen whatever was open last time (empty state -> nothing).
        self._restore_state()

    # --- ViewHost implementation -------------------------------------------

    def open_screen(self, name: str) -> None:
        """Push the registered screen ``name`` onto the screen stack."""
        self.push_screen(self.registry.create_screen(name))

    def open_view(self, name: str) -> None:
        """Open (or activate) the registered view ``name`` as a tab."""
        widget, title = self.registry.create_view(name)
        self.query_one(ContentArea).open(name, title, widget)
        self._views_changed()

    def close_view(self, name: str) -> None:
        """Close and destroy the open view ``name``, if any."""
        self.query_one(ContentArea).close(name)
        self._views_changed()

    def open_view_names(self) -> frozenset[str]:
        """Names of the currently-open content-area views."""
        return self.query_one(ContentArea).open_names

    def _sync_bars(self) -> None:
        """Show/hide header and footer items to match the open views."""
        names = self.open_view_names()
        self.query_one(AppHeader).sync_items(names)
        self.query_one(AppFooter).sync_items(names)

    def _views_changed(self) -> None:
        """React to the set of open views changing (refresh bars + save)."""
        self._sync_bars()
        self._persist_state()

    def _restore_state(self) -> None:
        """Reopen the views remembered from the last session."""
        for name in self.state.open_views:
            if not self.registry.has_widget(name):
                continue
            try:
                self.open_view(name)
            except Exception as exc:  # a broken view must not block startup
                logger.warning("Could not restore view {!r}: {}", name, exc)

    def _persist_state(self) -> None:
        """Save the currently-open views to the state file."""
        self.state = self.state.with_open_views(self.query_one(ContentArea).view_names)
        self.state_store.save(self.state)

    def _save_history(self, history: list[str]) -> None:
        """Save the REPL command history to the state file."""
        self.state = self.state.with_history(tuple(history))
        self.state_store.save(self.state)

    def clear_output(self) -> None:
        """Clear the REPL output pane."""
        self.query_one(Repl).clear_output()

    def reset_views(self) -> None:
        """Close every open view/screen and return to a clean base screen."""
        while len(self.screen_stack) > 1:
            self.pop_screen()
        self.query_one(ContentArea).close_all()
        self._views_changed()

    # --- Command palette ---------------------------------------------------

    async def run_command(self, name: str) -> None:
        """Run a registered command selected in the palette, via the REPL."""
        await self.query_one(Repl).run(name)

    # --- Actions -----------------------------------------------------------

    def action_pop_view(self) -> None:
        """Return from a pushed screen to the REPL (no-op on the base screen)."""
        if len(self.screen_stack) > 1:
            self.pop_screen()

    def action_close_view(self) -> None:
        """Close the active content-area view tab, if any."""
        content = self.query_one(ContentArea)
        name = content.active_name
        if name is not None:
            content.close(name)


def main() -> None:
    """Run the Toon application."""
    ToonApp().run()
