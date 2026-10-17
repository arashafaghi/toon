"""Textual application host and console entry point.

The host owns the ``App``, the overall layout, and the REPL lifetime. It
implements :class:`toon.api.ViewHost` so commands (built-in or plugin) can
navigate to registered UI contributions without touching app internals.

Layout (base screen): a persistent content area on top of the REPL. Widget
contributions mount into the content area; screen contributions are pushed onto
the Textual screen stack and popped again with ``Escape``.
"""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding

from toon.runtime.builtins import register_builtins
from toon.runtime.dispatcher import Dispatcher
from toon.runtime.registry import Registry
from toon.ui.content import ContentArea
from toon.ui.repl import Repl


class ToonApp(App[None]):
    """Interactive REPL host with local plugin support."""

    CSS = """
    Screen {
        layout: vertical;
    }

    #content {
        height: 1fr;
        border: round $panel;
    }

    #repl {
        height: 40%;
        border: round $accent;
    }

    #repl-log {
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("escape", "pop_view", "Back", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.registry = Registry()
        # Plugin loading arrives in M2; until then `plugins` reports none.
        register_builtins(self.registry, plugins=lambda: ())
        self.dispatcher = Dispatcher(self.registry)

    def compose(self) -> ComposeResult:
        yield ContentArea(id="content")
        yield Repl(self.dispatcher, self, id="repl")

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

    # --- Actions -----------------------------------------------------------

    def action_pop_view(self) -> None:
        """Return from a pushed screen to the REPL (no-op on the base screen)."""
        if len(self.screen_stack) > 1:
            self.pop_screen()


def main() -> None:
    """Run the Toon application."""
    ToonApp().run()
