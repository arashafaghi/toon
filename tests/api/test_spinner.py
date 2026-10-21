"""Behavior tests for the busy spinner (``toon.api.widgets.Spinner``)."""

from __future__ import annotations

import time
from collections.abc import Callable

import pytest
from textual.app import App, ComposeResult
from textual.pilot import Pilot
from textual.widget import Widget

from toon.api.widgets import (
    DEFAULT_SPINNER_PRESET,
    SPINNER_FRAMES,
    SPINNER_PRESETS,
    SPINNER_RANDOM_PRESETS,
    Spinner,
)

#: The presets requested for the demo, with their frame counts.
EXPECTED_PRESETS = {
    "dot_cycle": 8,
    "braille_random": 256,
    "z_arrow": 8,
    "z_b": 4,
    "z_d": 4,
    "z_bar": 4,
    "z_x": 2,
    "z_1": 4,
    "z_2": 4,
    "z_3": 4,
    "y_d": 4,
    "y_q": 4,
    "x_b": 4,
    "x_d": 4,
    "grow_a": 4,
    "grow_b": 4,
    "grow_c": 6,
    "grow_d": 12,
    "grow_e": 13,
}


class _SpinnerApp(App[None]):
    """Minimal host that mounts the widget(s) under test."""

    def __init__(self, *widgets: Widget) -> None:
        super().__init__()
        self._widgets = widgets

    def compose(self) -> ComposeResult:
        yield from self._widgets


async def _wait_until(
    pilot: Pilot[None], predicate: Callable[[], bool], *, timeout: float = 3.0
) -> None:
    """Poll ``predicate`` while letting the app process timers."""
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > deadline:
            raise AssertionError("condition was not met before the timeout")
        await pilot.pause(0.01)


def test_default_is_the_rotating_braille_spinner() -> None:
    assert DEFAULT_SPINNER_PRESET == "dot_cycle"
    assert SPINNER_FRAMES == ("⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷")
    assert SPINNER_FRAMES == SPINNER_PRESETS[DEFAULT_SPINNER_PRESET]


def test_every_requested_preset_is_available_with_one_cell_frames() -> None:
    assert set(SPINNER_PRESETS) == set(EXPECTED_PRESETS)
    for name, frame_count in EXPECTED_PRESETS.items():
        frames = SPINNER_PRESETS[name]
        assert len(frames) == frame_count, name
        assert frames, name
        assert all(len(frame) == 1 for frame in frames), name


def test_braille_random_covers_the_braille_block() -> None:
    assert "braille_random" in SPINNER_RANDOM_PRESETS
    frames = SPINNER_PRESETS["braille_random"]
    assert all(0x2800 <= ord(frame) <= 0x28FF for frame in frames)


def test_spinner_can_start_with_a_named_preset() -> None:
    spinner = Spinner(preset="z_arrow")

    assert spinner.preset == "z_arrow"
    assert spinner.frames == SPINNER_PRESETS["z_arrow"]
    assert spinner.randomize is False


def test_set_preset_switches_frames_at_runtime() -> None:
    spinner = Spinner(preset="z_arrow")

    spinner.set_preset("grow_d")

    assert spinner.preset == "grow_d"
    assert spinner.frames == SPINNER_PRESETS["grow_d"]
    assert str(spinner.render()) == SPINNER_PRESETS["grow_d"][0]


def test_unknown_preset_raises_a_helpful_error() -> None:
    with pytest.raises(ValueError, match="unknown spinner preset 'nope'"):
        Spinner(preset="nope")


def test_preset_and_frames_are_mutually_exclusive() -> None:
    with pytest.raises(ValueError, match="either preset= or frames="):
        Spinner(preset="z_x", frames=("a", "b"))


async def test_spinner_starts_hidden_and_cycles_frames_with_a_label() -> None:
    spinner = Spinner(interval=0.02)

    async with _SpinnerApp(spinner).run_test(size=(40, 5)) as pilot:
        await pilot.pause()
        assert spinner.is_spinning is False
        assert spinner.has_class("hidden")

        spinner.start("Fetching…")
        assert spinner.has_class("hidden") is False
        first = str(spinner.render())

        await _wait_until(pilot, lambda: str(spinner.render()) != first)

        assert spinner.is_spinning is True
        assert "Fetching…" in str(spinner.render())
        spinner.stop()


async def test_stop_freezes_the_frame_and_hides_the_spinner() -> None:
    spinner = Spinner(interval=0.02)

    async with _SpinnerApp(spinner).run_test(size=(40, 5)) as pilot:
        spinner.start()
        await pilot.pause(0.03)
        spinner.stop()

        frozen = str(spinner.render())
        await pilot.pause(0.1)

        assert str(spinner.render()) == frozen
        assert spinner.is_spinning is False
        assert spinner.has_class("hidden")


async def test_custom_frames_can_autostart_on_mount() -> None:
    spinner = Spinner(
        frames=(".", "..", "..."),
        interval=0.02,
        autostart=True,
        label="Loading",
    )

    async with _SpinnerApp(spinner).run_test(size=(40, 5)) as pilot:
        await pilot.pause()
        assert spinner.is_spinning is True
        assert spinner.has_class("hidden") is False

        await _wait_until(
            pilot, lambda: str(spinner.render()).split(" ", 1)[0] in {".", "..", "..."}
        )
        assert str(spinner.render()).endswith(" Loading")
        spinner.stop()


async def test_braille_random_picks_different_frames() -> None:
    spinner = Spinner(preset="braille_random", interval=0.005)

    async with _SpinnerApp(spinner).run_test(size=(40, 5)) as pilot:
        spinner.start()
        seen = {str(spinner.render())}
        deadline = time.monotonic() + 2.0
        while len(seen) < 3:
            assert time.monotonic() < deadline, "random frames did not vary"
            await pilot.pause(0.01)
            seen.add(str(spinner.render()))
        spinner.stop()

    assert spinner.randomize is True
    assert len(seen) >= 3
    assert all(0x2800 <= ord(frame) <= 0x28FF for frame in seen)
