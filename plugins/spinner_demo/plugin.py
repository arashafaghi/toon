"""Spinner demo plugin: preview every busy-indicator preset.

Two ways to see the spinner:

* ``spinner_demo`` opens a tab with a live spinner, a preset picker, and
  Start / Stop / Run 3s buttons.
* ``spinner_slow`` is an async command that waits (5s by default); the REPL
  shows its in-progress spinner above the input for the whole wait.

The presets themselves live in :mod:`toon.api.widgets` and are exported as
``SPINNER_PRESETS`` from ``toon.api``. The default is a rotating braille
spinner; ``braille_random`` picks a random braille character each tick.
"""

from __future__ import annotations

import asyncio
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.timer import Timer
from textual.widgets import Button, Select, Static

from toon.api import (
    DEFAULT_SPINNER_PRESET,
    SPINNER_PRESETS,
    Command,
    CommandContext,
    ExtensionRegistry,
    Spinner,
)

WIDGET_NAME = "spinner_demo"

#: How long the "Run 3s" button keeps the spinner running.
RUN_SECONDS = 3.0
#: Default wait for the ``spinner_slow`` command.
SLOW_SECONDS = 5.0


class SpinnerDemoWidget(Vertical):
    """Widget contribution: preview and control every spinner preset."""

    DEFAULT_CSS = """
    SpinnerDemoWidget {
        height: auto;
        padding: 1 2;
    }
    SpinnerDemoWidget .title {
        color: #58a6ff;
        text-style: bold;
        margin-bottom: 1;
    }
    SpinnerDemoWidget #demo-spinner {
        color: #d29922;
        height: 1;
    }
    SpinnerDemoWidget #demo-frames {
        color: #8b949e;
        height: auto;
        margin-top: 1;
    }
    SpinnerDemoWidget #demo-preset-row {
        height: auto;
        margin-top: 1;
    }
    SpinnerDemoWidget #demo-preset-row .label {
        width: 8;
        padding-top: 1;
        color: #8b949e;
    }
    SpinnerDemoWidget #demo-preset {
        width: 36;
    }
    SpinnerDemoWidget .hint {
        color: #8b949e;
        margin-top: 1;
    }
    SpinnerDemoWidget #demo-buttons {
        height: auto;
        margin-top: 1;
    }
    SpinnerDemoWidget #demo-buttons Button {
        margin-right: 1;
    }
    SpinnerDemoWidget #demo-status {
        color: #8b949e;
        margin-top: 1;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._run_timer: Timer | None = None

    def compose(self) -> ComposeResult:
        """Lay out the spinner, preset picker, controls, and preset list."""
        options = [(name, name) for name in SPINNER_PRESETS]
        yield Static("Busy spinner presets", classes="title")
        yield Spinner(
            preset=DEFAULT_SPINNER_PRESET,
            autostart=True,
            label="Working...",
            id="demo-spinner",
        )
        yield Static("", id="demo-frames")
        with Horizontal(id="demo-preset-row"):
            yield Static("Preset", classes="label")
            yield Select(
                options,
                value=DEFAULT_SPINNER_PRESET,
                allow_blank=False,
                id="demo-preset",
            )
        with Horizontal(id="demo-buttons"):
            yield Button("Start", id="demo-start", variant="success")
            yield Button("Stop", id="demo-stop", variant="error")
            yield Button("Run 3s", id="demo-run", variant="primary")
        yield Static("Spinning", id="demo-status")
        yield Static(
            "All presets: " + ", ".join(SPINNER_PRESETS),
            classes="hint",
        )

    def on_mount(self) -> None:
        """Show the default preset's frame information."""
        self._show_frames()

    def on_unmount(self) -> None:
        """Cancel a pending timed run when the tab closes.

        The spinner stops itself on unmount, so only the plugin-owned timer
        needs cleaning up here.
        """
        self._cancel_run()

    def on_select_changed(self, event: Select.Changed) -> None:
        """Switch the live preview to the chosen preset."""
        if event.select.id != "demo-preset" or event.value is Select.NULL:
            return
        preset = str(event.value)
        spinner = self.query_one(Spinner)
        spinner.set_preset(preset)
        if not spinner.is_spinning:
            spinner.start("Working...")
        self._show_frames()
        self.query_one("#demo-status", Static).update(f"Preset: {preset}")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Route the controls to the spinner."""
        event.stop()
        spinner = self.query_one(Spinner)
        status = self.query_one("#demo-status", Static)

        if event.button.id == "demo-start":
            self._cancel_run()
            spinner.start("Working...")
            status.update("Spinning")
        elif event.button.id == "demo-stop":
            self._cancel_run()
            spinner.stop()
            status.update("Stopped")
        elif event.button.id == "demo-run":
            self._cancel_run()
            spinner.start(f"Working for {RUN_SECONDS:g}s...")
            status.update(f"Running for {RUN_SECONDS:g}s")
            self._run_timer = self.set_timer(RUN_SECONDS, self._finish_run)

    def _show_frames(self) -> None:
        """Describe the current preset's frames under the spinner."""
        frames = self.query_one(Spinner).frames
        preview = " ".join(frames[:8])
        if len(frames) > 8:
            preview += " ..."
        self.query_one("#demo-frames", Static).update(f"{len(frames)} frames: {preview}")

    def _cancel_run(self) -> None:
        """Stop the pending "Run 3s" timer, if there is one."""
        if self._run_timer is not None:
            self._run_timer.stop()
            self._run_timer = None

    def _finish_run(self) -> None:
        """Stop the timed run and report completion."""
        self._run_timer = None
        self.query_one(Spinner).stop()
        self.query_one("#demo-status", Static).update("Done")


async def spinner_slow(ctx: CommandContext) -> str:
    """Wait so the REPL's in-progress spinner is clearly visible."""
    seconds = float(ctx.args[0]) if ctx.args else SLOW_SECONDS
    await asyncio.sleep(seconds)
    return f"Finished after {seconds:g}s."


def make_spinner_demo() -> SpinnerDemoWidget:
    """Return a *fresh* widget instance on every call."""
    return SpinnerDemoWidget()


def open_spinner_demo(ctx: CommandContext) -> str:
    """Open the spinner demo view."""
    ctx.host.open_view(WIDGET_NAME)
    return "Opened the spinner demo: pick a preset or use Start, Stop, Run 3s."


def register(registry: ExtensionRegistry) -> None:
    """Register the demo view and the commands that show the spinner."""
    registry.register_widget(
        WIDGET_NAME,
        make_spinner_demo,
        description="Preview every busy-spinner preset.",
        title="Spinner",
    )
    registry.register_command(
        Command("spinner_demo", open_spinner_demo, "Open the spinner demo view.")
    )
    registry.register_command(
        Command(
            "spinner_slow",
            spinner_slow,
            "Wait (default 5s) to show the REPL's in-progress spinner.",
        )
    )
