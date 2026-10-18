"""Arrow demo plugin: a plain moving arrow between two tasks.

Uses the shared :class:`~toon.api.FlowLane` / :class:`~toon.api.FlowTrack` from
the public API instead of its own animation code. A single ``▶`` / ``◀`` slides
along a track between ``Task A`` and ``Task B``.

Buttons pause/resume or restart; when it completes the tasks turn green.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Static

from toon.api import Command, CommandContext, ExtensionRegistry, FlowLane

WIDGET_NAME = "arrow_demo"

#: Seconds for one traversal.
TRAVEL_SECONDS = 1.2
#: Traversals before completion.
TRAVERSALS = 4


class ArrowDemoWidget(Vertical):
    """Widget contribution demonstrating a plain, smooth moving arrow."""

    DEFAULT_CSS = """
    ArrowDemoWidget {
        height: auto;
        padding: 1 2;
    }
    ArrowDemoWidget #arrow-status {
        height: 1;
        margin-top: 1;
        color: #8b949e;
    }
    ArrowDemoWidget #arrow-buttons {
        height: auto;
        margin-top: 1;
    }
    ArrowDemoWidget #arrow-buttons Button {
        margin-right: 1;
    }
    """

    def compose(self) -> ComposeResult:
        """Lay out the lane, a status line, and the controls."""
        yield FlowLane(
            source="Task A",
            sink="Task B",
            length=40,
            mode="ping-pong",
            duration=TRAVEL_SECONDS,
            traversals=TRAVERSALS,
        )
        yield Static("Running", id="arrow-status")
        with Horizontal(id="arrow-buttons"):
            yield Button("Pause", id="arrow-toggle", variant="warning")
            yield Button("Restart", id="arrow-restart")

    def on_mount(self) -> None:
        """Track global UI state."""
        self._paused = False

    # --- helpers -----------------------------------------------------------

    def _lane(self) -> FlowLane | None:
        return self.query_one_optional(FlowLane)

    def _toggle(self) -> Button:
        return self.query_one("#arrow-toggle", Button)

    def _set_status(self, text: str) -> None:
        self.query_one("#arrow-status", Static).update(text)

    def on_flow_lane_finished(self, _event: FlowLane.Finished) -> None:
        """Mark the whole widget done when the lane completes."""
        self.add_class("done")
        self._set_status("Complete")
        self._toggle().disabled = True

    # --- controls ----------------------------------------------------------

    async def _on_toggle(self) -> None:
        lane = self._lane()
        if lane is None:
            return
        if self._paused:
            self._paused = False
            lane.resume()
            self._toggle().label = "Pause"
            self._set_status("Running")
        else:
            self._paused = True
            await lane.pause()
            self._toggle().label = "Resume"
            self._set_status("Paused")

    async def _on_restart(self) -> None:
        lane = self._lane()
        if lane is None:
            return
        self._paused = False
        self.remove_class("done")
        toggle = self._toggle()
        toggle.disabled = False
        toggle.label = "Pause"
        self._set_status("Running")
        await lane.restart()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Route the two buttons to their actions."""
        event.stop()
        if event.button.id == "arrow-toggle":
            await self._on_toggle()
        elif event.button.id == "arrow-restart":
            await self._on_restart()


def make_arrow_demo() -> ArrowDemoWidget:
    """Return a *fresh* widget instance on every call."""
    return ArrowDemoWidget()


def show_arrow_demo(ctx: CommandContext) -> str:
    """Mount the arrow demo widget in the host content area."""
    ctx.host.show_widget(WIDGET_NAME)
    return "Opened the arrow demo: a plain moving arrow. Pause, resume, or restart."


def register(registry: ExtensionRegistry) -> None:
    """Register the widget and the command that opens it."""
    registry.register_widget(
        WIDGET_NAME,
        make_arrow_demo,
        description="Plain smooth moving arrow between two tasks.",
    )
    registry.register_command(
        Command("arrow_demo", show_arrow_demo, "Animate a plain arrow between two tasks.")
    )
