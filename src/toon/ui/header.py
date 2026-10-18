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


class AppHeader(Horizontal):
    """Header bar: the app title on the left, a live clock on the right."""

    def compose(self) -> ComposeResult:
        """Yield the header segments, left to right."""
        yield from self.build_segments()

    def build_segments(self) -> ComposeResult:
        """Yield the header's segments.

        Override or extend this to add more. The first segment is typically the
        title (it takes the remaining width); later segments sit on the right.
        """
        yield Static(self.app.title, id="header-title")
        yield Static("", id=CLOCK_ID)

    def on_mount(self) -> None:
        """Show the time immediately, then tick once a second."""
        clock = self.query_one(f"#{CLOCK_ID}", Static)
        clock.update(self._now())
        self.set_interval(1.0, lambda: clock.update(self._now()))

    @staticmethod
    def _now() -> str:
        """Return the current wall-clock time as text."""
        return datetime.now().strftime(TIME_FORMAT)
