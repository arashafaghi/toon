"""Host-owned content area where widget contributions are mounted.

The base screen keeps a persistent content pane above the REPL. Widget
contributions are factories returning a *fresh* :class:`~textual.widget.Widget`
instance on every call; the host removes the previously mounted contribution
and mounts the new one.

:meth:`ContentArea.set_widget` is invoked from
:meth:`toon.api.ViewHost.show_widget`, which is synchronous. Textual's
``remove_children`` and ``mount`` schedule their work on the running event loop
and return awaitables, so we deliberately do not await them and never create a
second event loop.
"""

from __future__ import annotations

from textual.containers import VerticalScroll
from textual.widget import Widget
from textual.widgets import Static


class ContentArea(VerticalScroll):
    """Host-owned pane on the base screen where widget contributions mount."""

    def set_widget(self, widget: Widget) -> None:
        """Replace the current content with the freshly created ``widget``."""
        self.clear_content()
        self.mount(widget)

    def clear_content(self) -> None:
        """Remove every child currently mounted in the content area."""
        self.remove_children()

    def show_message(self, text: str) -> None:
        """Display a simple placeholder or error message."""
        self.set_widget(Static(text))
