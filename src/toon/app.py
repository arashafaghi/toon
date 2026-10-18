"""Textual application host and console entry point.

The host owns the ``App``, the overall layout, and the REPL lifetime. It
implements :class:`toon.api.ViewHost` so commands (built-in or plugin) can
navigate to registered UI contributions without touching app internals.

Startup order is deliberate: built-in commands are registered *first* so a
plugin can never shadow ``help``/``clear``/``plugins``; then local plugins are
discovered under ``plugins/`` and loaded, with per-plugin failures reported in
the REPL. Layout (base screen): a persistent content area above the REPL.
"""

from __future__ import annotations

import os
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding

from toon.runtime.builtins import register_builtins
from toon.runtime.dispatcher import Dispatcher
from toon.runtime.plugin_loader import LoadReport, load_plugins
from toon.runtime.registry import Registry
from toon.ui.content import ContentArea
from toon.ui.palette import PaletteSystemCommands, build_commands
from toon.ui.repl import Repl

_PLUGINS_ENV = "TOON_PLUGINS_DIR"
_EMPTY_STATE_MESSAGE = "No active view. Run a command that opens a widget or a screen."


def _plugins_dir() -> Path:
    """Return the directory scanned for plugins (``./plugins`` by default)."""
    override = os.environ.get(_PLUGINS_ENV)
    return Path(override) if override else Path.cwd() / "plugins"


class ToonApp(PaletteSystemCommands, App[None]):
    """Interactive REPL host with local plugin support."""

    # Load styles from the external file
    CSS_PATH = "style.tcss"

    BINDINGS = [
        Binding("escape", "pop_view", "Back", show=False),
    ]

    # Command palette contents live in toon.ui.palette.
    COMMANDS = build_commands()

    def __init__(self, *, plugins_dir: Path | None = None) -> None:
        super().__init__()
        self.registry = Registry()
        # Built-ins first, so plugins cannot shadow them.
        self.load_report = LoadReport(())
        register_builtins(self.registry, plugins=lambda: self.load_report.summaries())
        self.load_report = load_plugins(plugins_dir or _plugins_dir(), self.registry)
        self.dispatcher = Dispatcher(self.registry)

    def compose(self) -> ComposeResult:
        yield ContentArea(id="content")
        yield Repl(self.dispatcher, self, id="repl")

    def on_mount(self) -> None:
        """Report the plugin load summary once the REPL is on screen."""
        repl = self.query_one(Repl)
        loaded = self.load_report.loaded_names
        if loaded:
            repl.write_output(f"Loaded {len(loaded)} plugin(s): {', '.join(loaded)}")
        for failure in self.load_report.failures:
            repl.write_output(f"[red]Plugin '{failure.name}' failed to load: {failure.error}[/red]")
        if not loaded and not self.load_report.failures:
            repl.write_output("No plugins found. Type 'help' for available commands.")
        self.query_one(ContentArea).show_message(_EMPTY_STATE_MESSAGE)

    # --- ViewHost implementation -------------------------------------------

    def open_screen(self, name: str) -> None:
        """Push the registered screen ``name`` onto the screen stack."""
        self.push_screen(self.registry.create_screen(name))

    def show_widget(self, name: str) -> None:
        """Mount a fresh instance of the registered widget ``name``."""
        self.query_one(ContentArea).set_widget(self.registry.create_widget(name))

    def clear_output(self) -> None:
        """Clear the REPL output pane."""
        self.query_one(Repl).clear_output()

    def reset_views(self) -> None:
        """Unload every UI contribution and return to a clean base screen."""
        while len(self.screen_stack) > 1:
            self.pop_screen()
        self.query_one(ContentArea).show_message(_EMPTY_STATE_MESSAGE)

    # --- Command palette ---------------------------------------------------

    async def run_command(self, name: str) -> None:
        """Run a registered command selected in the palette, via the REPL."""
        await self.query_one(Repl).run(name)

    # --- Actions -----------------------------------------------------------

    def action_pop_view(self) -> None:
        """Return from a pushed screen to the REPL (no-op on the base screen)."""
        if len(self.screen_stack) > 1:
            self.pop_screen()


def main() -> None:
    """Run the Toon application."""
    ToonApp().run()
