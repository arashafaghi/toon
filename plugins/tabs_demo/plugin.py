"""Tabs demo plugin: several views, each opened in its own content-area tab.

Shows off the host's tabbed view host from the public API:

* three independent widget contributions (``alpha``, ``beta``, ``gamma``);
* ``tabs_demo`` opens all three at once, so you see several tabs coexist;
* ``tabs_open <name>`` opens one (and **activates** it if already open);
* ``tabs_close`` closes them all, and ``Ctrl+W`` closes the active tab.

Each view is a real widget instance that is destroyed when its tab is closed.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from toon.api import Command, CommandContext, ExtensionRegistry

#: ``(view name, tab title, border colour, blurb)``.
VIEWS: tuple[tuple[str, str, str, str], ...] = (
    ("alpha", "Alpha", "#58a6ff", "The first view. Its own tab."),
    ("beta", "Beta", "#3fb950", "The second view. Independent of Alpha."),
    ("gamma", "Gamma", "#d29922", "The third view. All three can be open at once."),
)

_NAMES = tuple(name for name, *_ in VIEWS)


class DemoView(Vertical):
    """A self-contained view contribution; one instance per open tab."""

    DEFAULT_CSS = """
    DemoView {
        height: auto;
        padding: 1 2;
    }
    DemoView .demo-view-title {
        text-style: bold;
    }
    DemoView .demo-view-blurb {
        margin-top: 1;
    }
    DemoView .demo-view-hint {
        margin-top: 1;
        color: #8b949e;
    }
    """

    def __init__(self, label: str, colour: str, blurb: str) -> None:
        super().__init__()
        self._label = label
        self._colour = colour
        self._blurb = blurb

    def on_mount(self) -> None:
        """Give this view its own border colour."""
        self.styles.border = ("round", self._colour)

    def compose(self) -> ComposeResult:
        """Yield this view's body."""
        yield Static(f"[bold {self._colour}]{self._label} view[/]", classes="demo-view-title")
        yield Static(self._blurb, classes="demo-view-blurb")
        yield Static(
            "This is its own tab, not a shared screen. "
            "Switch tabs, open another view, or press Ctrl+W to close.",
            classes="demo-view-hint",
        )


def _make_view(label: str, colour: str, blurb: str):
    """Return a zero-argument factory producing a *fresh* view each call."""

    def factory() -> DemoView:
        return DemoView(label, colour, blurb)

    return factory


# --- commands --------------------------------------------------------------


def open_all(ctx: CommandContext) -> str:
    """Open every demo view as a tab."""
    for name, *_ in VIEWS:
        ctx.host.open_view(name)
    return f"Opened {len(VIEWS)} views as tabs: {', '.join(_NAMES)}."


def open_one(ctx: CommandContext) -> str:
    """Open (or activate) a single demo view named in the arguments."""
    if not ctx.args:
        return f"Usage: tabs_open <name>   (names: {', '.join(_NAMES)})"
    name = ctx.args[0]
    if name not in _NAMES:
        return f"No demo view named '{name}'. Names: {', '.join(_NAMES)}"
    ctx.host.open_view(name)
    return f"Opened view '{name}' (activated if it was already open)."


def close_all(ctx: CommandContext) -> str:
    """Close every demo view."""
    for name, *_ in VIEWS:
        ctx.host.close_view(name)
    return "Closed all demo views."


def register(registry: ExtensionRegistry) -> None:
    """Register the three views and the commands that open/close them."""
    for name, label, colour, blurb in VIEWS:
        registry.register_widget(
            name,
            _make_view(label, colour, blurb),
            description=blurb,
            title=label,
        )
    registry.register_command(Command("tabs_demo", open_all, "Open all demo views as tabs."))
    registry.register_command(Command("tabs_open", open_one, "Open one demo view by name."))
    registry.register_command(Command("tabs_close", close_all, "Close all demo views."))
