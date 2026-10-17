"""Example UI plugin: contribute a widget and a screen to the host.

This is the reference UI extension from M3 of ``roadmap.md``. It registers both
a widget and a screen plus one command for each, so a user can reach plugin UI
from the REPL. It imports only :mod:`toon.api` for host contracts and Textual
for the UI classes; it never touches host internals.

Navigation goes exclusively through ``CommandContext.host`` -- the host owns
the app layout, mounts widget contributions in its content area, and pushes
screen contributions onto the screen stack (``Escape`` pops back to the REPL).
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Static

from toon.api import Command, CommandContext, ExtensionRegistry

WIDGET_NAME = "demo_widget"
SCREEN_NAME = "demo_screen"


class DemoWidget(Vertical):
    """Widget contribution mounted in the host's designated content area."""

    def compose(self) -> ComposeResult:
        """Yield the widget's static body."""
        yield Static(
            "Widget contribution from the ui_demo plugin",
            id="ui-demo-widget-title",
        )
        yield Static(
            "Run 'demo_screen' to open the full-screen view.",
            id="ui-demo-widget-hint",
        )


class DemoScreen(Screen[None]):
    """Full-screen contribution pushed onto the host's screen stack."""

    def compose(self) -> ComposeResult:
        """Yield a title and the return-to-REPL hint."""
        yield Static(
            "Screen contribution from the ui_demo plugin",
            id="ui-demo-screen-title",
        )
        yield Static(
            "Press Escape to return to the REPL",
            id="ui-demo-screen-hint",
        )


def make_demo_widget() -> DemoWidget:
    """Return a *fresh* :class:`DemoWidget` on every call."""
    return DemoWidget()


def make_demo_screen() -> DemoScreen:
    """Return a *fresh* :class:`DemoScreen` on every call."""
    return DemoScreen()


def demo_widget(ctx: CommandContext) -> str:
    """Show the ``demo_widget`` contribution in the host content area."""
    ctx.host.show_widget(WIDGET_NAME)
    return f"Showing the '{WIDGET_NAME}' widget in the content area."


def demo_screen(ctx: CommandContext) -> str:
    """Open the ``demo_screen`` contribution as a full-screen view."""
    ctx.host.open_screen(SCREEN_NAME)
    return "Opened the 'demo_screen' view. Press Escape to return to the REPL."


def register(registry: ExtensionRegistry) -> None:
    """Register the widget, screen, and their commands."""
    registry.register_widget(
        WIDGET_NAME,
        make_demo_widget,
        description="Example widget shown in the host content area.",
    )
    registry.register_screen(
        SCREEN_NAME,
        make_demo_screen,
        description="Example full-screen view (Escape returns to the REPL).",
    )
    registry.register_command(
        Command(
            "demo_widget",
            demo_widget,
            description="Show the ui_demo widget in the content area.",
        )
    )
    registry.register_command(
        Command(
            "demo_screen",
            demo_screen,
            description="Open the ui_demo full-screen view.",
        )
    )
