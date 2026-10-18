"""Host-owned content area: a tabbed host for widget contributions.

Every widget a plugin opens via ``ViewHost.open_view`` gets its own tab here.
The host holds no per-plugin knowledge: it mounts a fresh widget per view,
**activates** a view that is already open instead of duplicating it, and
**destroys** the widget when the view is closed. Screens are separate (pushed
onto the screen stack); this area is the persistent pane above the REPL.
"""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import Static, TabbedContent, TabPane

_EMPTY_STATE = "No view open. Run a command that opens a view."


class ContentArea(Vertical):
    """Tabbed host for widget contributions mounted above the REPL."""

    DEFAULT_CSS = """
    ContentArea TabbedContent {
        height: 1fr;
    }
    ContentArea #view-empty {
        height: 1fr;
        content-align: center middle;
        color: #8b949e;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        #: Open views, mapping the registration name to the tab's pane id.
        self._open: dict[str, str] = {}

    def compose(self) -> ComposeResult:
        """A tab container plus an empty-state message."""
        yield TabbedContent(id="view-tabs")
        yield Static(_EMPTY_STATE, id="view-empty")

    def on_mount(self) -> None:
        """Show the empty state (no views are open yet)."""
        self._sync_empty()

    # --- public API (used by the host) -------------------------------------

    def open(self, name: str, title: str, widget: Widget) -> None:
        """Open the view ``name`` in a new tab, or activate it if already open."""
        if name in self._open:
            self._tabs().active = self._open[name]
            return
        pane_id = f"view-{name}"
        self._tabs().add_pane(TabPane(title, widget, id=pane_id))
        self._open[name] = pane_id
        self._tabs().active = pane_id
        self._sync_empty()

    def close(self, name: str) -> None:
        """Close and destroy the view ``name`` if it is open."""
        pane_id = self._open.pop(name, None)
        if pane_id is not None:
            self._tabs().remove_pane(pane_id)
        self._sync_empty()

    def close_all(self) -> None:
        """Close and destroy every open view."""
        for pane_id in list(self._open.values()):
            self._tabs().remove_pane(pane_id)
        self._open.clear()
        self._sync_empty()

    def has(self, name: str) -> bool:
        """Whether the view ``name`` is currently open."""
        return name in self._open

    @property
    def open_names(self) -> frozenset[str]:
        """Names of every currently-open view."""
        return frozenset(self._open)

    @property
    def view_names(self) -> tuple[str, ...]:
        """Open view names, in the order they were opened."""
        return tuple(self._open)

    @property
    def active_name(self) -> str | None:
        """The name of the active view, or ``None`` when nothing is open."""
        active = self._tabs().active
        for name, pane_id in self._open.items():
            if pane_id == active:
                return name
        return None

    # --- internals ---------------------------------------------------------

    def _tabs(self) -> TabbedContent:
        return self.query_one(TabbedContent)

    def _sync_empty(self) -> None:
        tabs = self._tabs()
        empty = self.query_one("#view-empty", Static)
        has_views = bool(self._open)
        tabs.display = has_views
        empty.display = not has_views
