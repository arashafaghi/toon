"""Behavior tests for the public animation widgets (``toon.api.widgets``)."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import pytest
from textual.app import App, ComposeResult
from textual.pilot import Pilot
from textual.widget import Widget

from toon.api.widgets import FlowLane, FlowTrack, render_track

# --------------------------------------------------------------------------- #
# render_track: pure rendering
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("phase", "direction", "expected"),
    [
        (0.0, 1, "▶····"),
        (0.5, 1, "··▶··"),
        (1.0, 1, "····▶"),
        (0.0, -1, "◀····"),
        (0.5, -1, "··◀··"),
        (1.0, -1, "····◀"),
    ],
)
def test_render_track_arrow_position_and_direction(
    phase: float, direction: int, expected: str
) -> None:
    assert render_track(phase, direction, 5) == expected


@pytest.mark.parametrize("phase", [-1.0, 2.0])
def test_render_track_clamps_phase_to_the_track(phase: float) -> None:
    rendered = render_track(phase, 1, 5)
    assert len(rendered) == 5
    assert rendered.count("▶") == 1


# --------------------------------------------------------------------------- #
# FlowTrack / FlowLane behavior under App.run_test
# --------------------------------------------------------------------------- #


class _WidgetApp(App[None]):
    """Minimal host that mounts the widget(s) under test."""

    def __init__(self, *widgets: Widget) -> None:
        super().__init__()
        self._widgets = widgets

    def compose(self) -> ComposeResult:
        yield from self._widgets


class _LaneApp(_WidgetApp):
    """Host that counts the ``FlowLane.Finished`` messages it receives."""

    def __init__(self, lane: FlowLane) -> None:
        super().__init__(lane)
        self.finished = 0

    def on_flow_lane_finished(self, event: FlowLane.Finished) -> None:
        self.finished += 1


async def _wait_until(
    pilot: Pilot[None], predicate: Callable[[], bool], *, timeout: float = 5.0
) -> None:
    """Poll ``predicate`` while letting the app process timers/animations."""
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > deadline:
            raise AssertionError("condition was not met before the timeout")
        await pilot.pause(0.02)


async def test_ping_pong_reverses_at_the_end() -> None:
    track = FlowTrack(length=6, mode="ping-pong", duration=0.02, traversals=2)
    app = _WidgetApp(track)

    async with app.run_test(size=(40, 8)) as pilot:
        await _wait_until(pilot, lambda: track.is_done)

        assert track.is_done is True
        assert track.direction == -1
        assert track.phase == pytest.approx(0.0)


async def test_one_way_loops_back_to_the_start() -> None:
    track = FlowTrack(length=6, mode="one-way", duration=0.02, traversals=2)
    app = _WidgetApp(track)

    async with app.run_test(size=(40, 8)) as pilot:
        await _wait_until(pilot, lambda: track.is_done)

        assert track.is_done is True
        assert track.direction == 1
        assert track.phase == pytest.approx(1.0)


async def test_track_calls_on_finished_and_marks_done() -> None:
    track = FlowTrack(length=6, duration=0.02, traversals=1)
    finished: list[Any] = []
    track.on_finished = lambda: finished.append("done")
    app = _WidgetApp(track)

    async with app.run_test(size=(40, 8)) as pilot:
        await _wait_until(pilot, lambda: track.is_done)

        assert finished == ["done"]
        assert track.is_done is True
        assert track.has_class("done")


async def test_pause_freezes_the_track_and_resume_continues() -> None:
    track = FlowTrack(length=20, duration=0.8, traversals=3)
    app = _WidgetApp(track)

    async with app.run_test(size=(40, 8)) as pilot:
        await pilot.pause(0.1)
        await track.pause()
        frozen = track.phase
        assert 0.0 < frozen < 1.0

        await pilot.pause(0.15)
        assert track.phase == frozen
        assert track.is_done is False

        track.resume()
        await pilot.pause(0.15)
        assert track.phase > frozen


async def test_restart_returns_to_the_start() -> None:
    track = FlowTrack(length=20, duration=0.8, traversals=3)
    app = _WidgetApp(track)

    async with app.run_test(size=(40, 8)) as pilot:
        await pilot.pause(0.1)
        assert track.phase > 0.0

        await track.restart()

        assert track.phase == 0.0
        assert track.is_done is False


async def test_lane_posts_finished_when_complete() -> None:
    lane = FlowLane("lane", source="a", sink="b", length=8, duration=0.02, traversals=1)
    app = _LaneApp(lane)

    async with app.run_test(size=(60, 8)) as pilot:
        await _wait_until(pilot, lambda: lane.is_done)
        await _wait_until(pilot, lambda: app.finished > 0)

        assert app.finished == 1
        assert lane.is_done is True
        assert lane.has_class("done")
