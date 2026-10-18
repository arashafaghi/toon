"""Application header (host-owned; no plugin required).

A thin bar with the app title on the left and a live clock on the right. It is
deliberately simple to extend: add, remove, or reorder segments in
:meth:`AppHeader.build_segments` (or override it in a subclass) and style them
in ``style.tcss``. Each yielded widget becomes a column in the bar.
"""

from __future__ import annotations

from datetime import datetime

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static

__all__ = ["CLOCK_ID", "TIME_FORMAT", "AppHeader"]

#: ``strftime`` format used by the header clock.
TIME_FORMAT = "%H:%M:%S"

#: Widget id of the clock segment.
CLOCK_ID = "header-clock"


#: Widget id of the container holding plugin header items.
ITEMS_ID = "header-items"


class AppHeader(Horizontal):
    """Header bar: title, plugin items, and a live clock."""

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._items: dict[str, object] = {}

    def compose(self) -> ComposeResult:
        """Yield the header segments, left to right."""
        yield from self.build_segments()

    def build_segments(self) -> ComposeResult:
        """Yield the header's segments, left to right.

        The title takes the remaining width; plugin header items live in a
        dedicated container (so they can appear/disappear with their view);
        the clock sits last. Override or extend this for more host segments.
        """
        yield Static(self.app.title, id="header-title")
        yield Horizontal(id=ITEMS_ID)
        yield Static("", id=CLOCK_ID)

    def on_mount(self) -> None:
        """Show the time immediately, then tick once a second."""
        clock = self.query_one(f"#{CLOCK_ID}", Static)
        clock.update(self._now())
        self.set_interval(1.0, lambda: clock.update(self._now()))

    def sync_items(self, open_views: frozenset[str]) -> None:
        """Show the header items whose view is open (session items always)."""
        container = self.query_one(f"#{ITEMS_ID}", Horizontal)
        wanted = {
            item.name: item
            for item in self.app.registry.header_items()
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

    @staticmethod
    def _now() -> str:
        """Return the current wall-clock time as text."""
        return datetime.now().strftime(TIME_FORMAT)
