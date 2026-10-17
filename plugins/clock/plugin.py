"""Example UI plugin: a live clock widget that mounts into the content panel.

Run the ``clock`` command in the REPL to mount a self-updating clock widget in
the host content area. Run ``clock_screen`` to open the same clock as a
full-screen view (press Escape to return to the REPL).

This plugin imports only :mod:`toon.api` for the host contract and Textual for
the UI classes -- it never touches host internals. Navigation goes exclusively
through ``CommandContext.host``.
"""

from __future__ import annotations

from datetime import datetime

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Static

from toon.api import Command, CommandContext, ExtensionRegistry

WIDGET_NAME = "clock"
SCREEN_NAME = "clock_screen"


class ClockWidget(Vertical):
    """A live clock that refreshes once per second while mounted."""

    DEFAULT_CSS = """
    ClockWidget {
        width: 30;
        height: 10;
        padding: 1 2;
        border: round #58a6ff;
        background: #161b22;
    }
    ClockWidget #clock-face {
        color: #58a6ff;
        text-style: bold;
    }
    ClockWidget #clock-label {
        color: #8b949e;
    }
    """

    def compose(self) -> ComposeResult:
        """Yield a label and the plain-text clock face."""
        yield Static(self._now(), id="clock-face")

    def on_mount(self) -> None:
        """Start a 1-second repeating timer that updates the clock face."""
        self.set_interval(1.0, self._refresh)

    def _refresh(self) -> None:
        """Update the clock face with the current time."""
        self.query_one("#clock-face", Static).update(self._now())

    @staticmethod
    def _now() -> str:
        """Return the current local time as ``HH:MM:SS``."""
        return datetime.now().strftime("%H:%M:%S")


class ClockScreen(Screen[None]):
    """Full-screen view that hosts a fresh clock widget."""

    def compose(self) -> ComposeResult:
        """Yield the clock widget and a return-to-REPL hint."""
        yield ClockWidget()
        yield Static("Press Escape to return to the REPL", id="clock-screen-hint")


def make_clock_widget() -> ClockWidget:
    """Return a *fresh* :class:`ClockWidget` on every call."""
    return ClockWidget()


def make_clock_screen() -> ClockScreen:
    """Return a *fresh* :class:`ClockScreen` on every call."""
    return ClockScreen()


def show_clock(ctx: CommandContext) -> str:
    """Mount the clock widget in the host content panel."""
    ctx.host.show_widget(WIDGET_NAME)
    return "Clock mounted in the content panel."


def open_clock_screen(ctx: CommandContext) -> str:
    """Open the clock as a full-screen view."""
    ctx.host.open_screen(SCREEN_NAME)
    return "Opened the clock screen. Press Escape to return to the REPL."


def register(registry: ExtensionRegistry) -> None:
    """Register the clock widget, screen, and their commands."""
    registry.register_widget(
        WIDGET_NAME,
        make_clock_widget,
        description="A live clock mounted in the content panel.",
    )
    registry.register_screen(
        SCREEN_NAME,
        make_clock_screen,
        description="A live clock as a full-screen view (Escape returns).",
    )
    registry.register_command(
        Command("clock", show_clock, description="Show a live clock in the content panel.")
    )
    registry.register_command(
        Command(
            "clock_screen",
            open_clock_screen,
            description="Open a live clock as a full-screen view.",
        )
    )
