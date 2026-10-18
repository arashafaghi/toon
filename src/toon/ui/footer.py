"""Application footer (host-owned; no plugin required).

A thin wrapper that shows Textual's :class:`~textual.widgets.Footer` (which
automatically lists every *visible* key binding and the command-palette hint)
alongside plugin-contributed footer items.

Adding a shortcut to the footer therefore means only one thing: add a binding to
``ToonApp.BINDINGS``. To add non-binding hints (text labels), extend
:attr:`AppFooter.EXTRA_HINTS`; plugins contribute widgets with
``ExtensionRegistry.register_footer_item`` (session-wide, or tied to a view).
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Footer, Static

__all__ = ["AppFooter"]

#: Widget id of the container holding plugin footer items.
ITEMS_ID = "footer-items"


class AppFooter(Horizontal):
    """Footer bar: Textual's key bindings plus plugin-contributed items."""

    DEFAULT_CSS = """
    AppFooter {
        height: 1;
    }
    AppFooter Footer {
        width: 1fr;
    }
    AppFooter #footer-items {
        width: auto;
        height: 1;
    }
    """

    #: Extra static hints appended after the bindings (empty by default).
    #: Example: ``EXTRA_HINTS = ("esc back", "? help")``.
    EXTRA_HINTS: tuple[str, ...] = ()

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._items: dict[str, object] = {}

    def compose(self) -> ComposeResult:
        """Textual's footer, optional hints, then the plugin-items container."""
        yield Footer(id="footer-keys")
        for hint in self.EXTRA_HINTS:
            yield Static(hint, classes="footer-hint")
        yield Horizontal(id=ITEMS_ID)

    def sync_items(self, open_views: frozenset[str]) -> None:
        """Show the footer items whose view is open (session items always)."""
        container = self.query_one(f"#{ITEMS_ID}", Horizontal)
        wanted = {
            item.name: item
            for item in self.app.registry.footer_items()
            if item.view is None or item.view in open_views
        }
        for name, widget in self._items.items():
            if name not in wanted:
                widget.remove()
        self._items = {name: widget for name, widget in self._items.items() if name in wanted}
        for name, item in wanted.items():
            if name not in self._items:
                widget = item.factory()
                self._items[name] = widget
                container.mount(widget)
