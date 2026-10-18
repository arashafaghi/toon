"""Example plugin: a single button that emits one log record per level.

Demonstrates :mod:`toon.api` logging. The widget contributes a single button;
pressing it writes **DEBUG**, **INFO**, **WARNING**, and **ERROR** records,
which the host renders live in the REPL output area (colour-coded by level).
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Button

from toon.api import Command, CommandContext, ExtensionRegistry, logger

WIDGET_NAME = "log_demo"


class LogDemoWidget(Vertical):
    """Content-area widget that contains one button."""

    def compose(self) -> ComposeResult:
        """Yield the one and only button."""
        yield Button("Log 4 levels", id="log-demo-button", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Emit one log record at each of four levels."""
        event.stop()
        logger.debug("DEBUG: button pressed in the log_demo plugin")
        logger.info("INFO: button pressed in the log_demo plugin")
        logger.warning("WARNING: button pressed in the log_demo plugin")
        logger.error("ERROR: button pressed in the log_demo plugin")


def make_log_demo_widget() -> LogDemoWidget:
    """Return a *fresh* widget instance on every call."""
    return LogDemoWidget()


def show_log_demo(ctx: CommandContext) -> str:
    """Mount the logging demo widget in the host content area."""
    ctx.host.open_view(WIDGET_NAME)
    return "Opened the log demo widget. Press the button to emit logs."


def register(registry: ExtensionRegistry) -> None:
    """Register the widget and the command that opens it."""
    registry.register_widget(
        WIDGET_NAME,
        make_log_demo_widget,
        description="Single button that logs four levels.",
        title="Log demo",
    )
    registry.register_command(Command("log_demo", show_log_demo, "Open the logging demo widget."))
