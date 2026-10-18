"""Reusable Textual widgets for plugin UI contributions.

This is the UI-facing half of the public extension API. Plugins import from here
to build animated flows without re-implementing the animation machinery::

    from toon.api import FlowLane          # lazy re-export
    from toon.api.widgets import FlowTrack # or import the module directly

Importing this module pulls in Textual. ``toon.api`` itself stays Textual-free
at runtime -- it exposes these names lazily so the core runtime never imports
Textual.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Static

__all__ = [
    "FlowLane",
    "FlowMode",
    "FlowTrack",
    "Orientation",
    "TrackStyle",
    "render_track",
]

#: Axis the marker travels along.
Orientation = Literal["horizontal", "vertical"]
#: ``"arrow"`` is a plain marker; ``"comet"`` adds a sub-cell body and a tail.
TrackStyle = Literal["arrow", "comet"]
#: ``"ping-pong"`` reverses at each end; ``"one-way"`` loops to the start.
FlowMode = Literal["ping-pong", "one-way"]

_DOTS = "·"
_EIGHTHS = "▏▎▍▌▋▊▉█"
_TAIL = "▓▒░"


def render_track(
    phase: float,
    direction: int,
    length: int,
    *,
    orientation: Orientation = "horizontal",
    style: TrackStyle = "arrow",
) -> str:
    """Render one flow-track frame as text (newline-joined when vertical).

    Args:
        phase: Fractional progress, ``0.0`` (start) to ``1.0`` (end).
        direction: Positive travels "forward" (down/right), negative reverses.
        length: Number of cells (or rows) in the track.
        orientation: ``"horizontal"`` or ``"vertical"``.
        style: ``"arrow"`` or ``"comet"``.

    Returns:
        The track as a string (a single line, or multiple lines when vertical).
    """
    position = min(1.0, max(0.0, phase)) * (length - 1)
    head = min(length - 1, max(0, int(position)))
    fraction = position - head
    forward = direction >= 0

    if orientation == "vertical":
        return _render_vertical(head, fraction, forward, length, style)
    return _render_horizontal(head, fraction, forward, length, style)


def _render_horizontal(
    head: int, fraction: float, forward: bool, length: int, style: TrackStyle
) -> str:
    cells = [_DOTS] * length
    cells[head] = "▶" if forward else "◀"
    if style == "comet":
        step = -1 if forward else 1
        _decorate(cells, head, fraction, step, length, horizontal=True)
    return "".join(cells)


def _render_vertical(
    head: int, fraction: float, forward: bool, length: int, style: TrackStyle
) -> str:
    cells = [_DOTS] * length
    cells[head] = "▼" if forward else "▲"
    if style == "comet":
        step = 1 if forward else -1  # travel direction; the body trails behind
        _decorate(cells, head, fraction, -step, length, horizontal=False, forward=forward)
    return "\n".join(cells)


def _decorate(
    cells: list[str],
    head: int,
    fraction: float,
    step: int,
    length: int,
    *,
    horizontal: bool,
    forward: bool = True,
) -> None:
    """Add the sub-cell body and fading tail behind the arrow in ``cells``."""
    body = head + step
    if 0 <= body < length:
        size = 1.0 - fraction
        if horizontal:
            eighths = min(8, max(0, round(size * 8)))
            if eighths >= 1:
                cells[body] = _EIGHTHS[eighths - 1]
        else:
            cells[body] = _body_char(forward, size)
    for offset, char in enumerate(_TAIL, start=2):
        index = head + step * offset
        if 0 <= index < length:
            cells[index] = char


def _body_char(forward: bool, size: float) -> str:
    if size > 0.66:
        return "█"
    if forward:  # moving down: the body trails above (upper blocks)
        return "▀" if size > 0.33 else "▔"
    return "▄" if size > 0.33 else "▁"  # moving up: lower blocks


class FlowTrack(Static):
    """A track with an animated marker that travels along it.

    Reusable across plugins. It owns the animation state machine
    (:meth:`start`, :meth:`pause`, :meth:`resume`, :meth:`restart`), exposes
    :attr:`is_done`, calls ``on_finished`` when complete, and only repaints when
    the rendered frame changes.
    """

    DEFAULT_CSS = """
    FlowTrack {
        width: auto;
        height: auto;
        color: #58a6ff;
    }
    FlowTrack.done {
        color: #3fb950;
    }
    """

    phase = reactive(0.0, layout=False)
    direction = reactive(1, layout=False)

    def __init__(
        self,
        *,
        length: int = 32,
        orientation: Orientation = "horizontal",
        style: TrackStyle = "arrow",
        mode: FlowMode = "ping-pong",
        duration: float = 1.4,
        traversals: int = 3,
        easing: str = "linear",
        **kwargs: object,
    ) -> None:
        super().__init__("", **kwargs)
        self._length = max(2, length)
        self._orientation = orientation
        self._style = style
        self._mode = mode
        self._duration = duration
        self._traversals = max(1, traversals)
        self._easing = easing
        self._count = 0
        self._is_running = False
        self._done = False
        self._last = ""
        self.on_finished: Callable[[], None] | None = None

    # --- lifecycle ---------------------------------------------------------

    def on_mount(self) -> None:
        """Render the first frame and start moving."""
        self._repaint()
        self.start()

    def watch_phase(self, _value: float) -> None:
        """Re-render whenever the animation advances the phase."""
        self._repaint()

    def watch_direction(self, _value: int) -> None:
        """Re-render whenever the travel direction flips."""
        self._repaint()

    @property
    def is_done(self) -> bool:
        """Whether the track has completed all its traversals."""
        return self._done

    # --- control -----------------------------------------------------------

    def start(self) -> None:
        """Reset to the beginning and animate."""
        self.remove_class("done")
        self._count = 0
        self._done = False
        self._is_running = True
        self.direction = 1
        self.phase = 0.0
        self._run_animation(self._duration)

    async def pause(self) -> None:
        """Freeze the marker where it is."""
        self._is_running = False
        await self.stop_animation("phase", complete=False)

    def resume(self) -> None:
        """Continue to the current target (over the remaining time)."""
        self._is_running = True
        remaining = max(0.05, self._duration * abs(self._target() - self.phase))
        self._run_animation(remaining)

    async def restart(self) -> None:
        """Stop and start over."""
        await self.stop_animation("phase", complete=False)
        self.start()

    # --- internals ---------------------------------------------------------

    def _target(self) -> float:
        if self._mode == "one-way":
            return 1.0
        return 1.0 if self.direction >= 0 else 0.0

    def _run_animation(self, duration: float) -> None:
        self.animate(
            "phase",
            self._target(),
            duration=duration,
            easing=self._easing,
            on_complete=self._on_complete,
        )

    def _on_complete(self) -> None:
        if not self._is_running:
            return
        self._count += 1
        if self._count >= self._traversals:
            self._finish()
            return
        if self._mode == "one-way":
            self.phase = 0.0
        else:
            self.direction = -self.direction
        self._run_animation(self._duration)

    def _finish(self) -> None:
        self._is_running = False
        self._done = True
        self.add_class("done")
        if self.on_finished is not None:
            self.on_finished()

    async def on_unmount(self) -> None:
        """Stop any in-flight animation when the track is removed."""
        await self.stop_animation("phase", complete=False)

    def _repaint(self) -> None:
        text = render_track(
            self.phase,
            self.direction,
            self._length,
            orientation=self._orientation,
            style=self._style,
        )
        if text != self._last:  # only touch the DOM when the frame changes
            self._last = text
            self.update(text)


class FlowLane(Horizontal):
    """A labelled flow row: optional name, two tasks, and a :class:`FlowTrack`.

    Delegates animation control to its track and posts :class:`FlowLane.Finished`
    when the track completes.
    """

    DEFAULT_CSS = """
    FlowLane {
        height: 3;
    }
    FlowLane .flow-lane-name {
        width: 13;
        height: 3;
        content-align: left middle;
        color: #8b949e;
    }
    FlowLane .flow-lane-task {
        width: 12;
        height: 3;
        content-align: center middle;
        border: round #30363d;
        background: #161b22;
        color: #c9d1d9;
    }
    FlowLane FlowTrack {
        height: 3;
        content-align: center middle;
    }
    FlowLane.done .flow-lane-task {
        border: round #3fb950;
        background: #0f2a17;
        color: #3fb950;
        text-style: bold;
    }
    """

    class Finished(Message):
        """Posted when this lane's flow completes."""

    def __init__(
        self,
        label: str | None = None,
        *,
        source: str | None = None,
        sink: str | None = None,
        length: int = 32,
        orientation: Orientation = "horizontal",
        style: TrackStyle = "arrow",
        mode: FlowMode = "ping-pong",
        duration: float = 1.4,
        traversals: int = 3,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self._label = label
        self._source = source
        self._sink = sink
        self._track_config = {
            "length": length,
            "orientation": orientation,
            "style": style,
            "mode": mode,
            "duration": duration,
            "traversals": traversals,
        }

    def compose(self) -> ComposeResult:
        """Lay out the name, source task, track, and sink task."""
        if self._label is not None:
            yield Static(self._label, classes="flow-lane-name")
        if self._source is not None:
            yield Static(self._source, classes="flow-lane-task")
        yield FlowTrack(**self._track_config)
        if self._sink is not None:
            yield Static(self._sink, classes="flow-lane-task")

    def on_mount(self) -> None:
        """Hook the track's completion callback."""
        track = self.track
        if track is not None:
            track.on_finished = self._on_track_finished

    @property
    def track(self) -> FlowTrack | None:
        """This lane's :class:`FlowTrack`, if mounted."""
        return self.query_one_optional(FlowTrack)

    @property
    def is_done(self) -> bool:
        """Whether this lane's flow completed."""
        track = self.track
        return track.is_done if track is not None else False

    def start(self) -> None:
        """Start this lane's flow."""
        track = self.track
        if track is not None:
            track.start()

    async def pause(self) -> None:
        """Pause this lane's flow."""
        track = self.track
        if track is not None:
            await track.pause()

    def resume(self) -> None:
        """Resume this lane's flow."""
        track = self.track
        if track is not None:
            track.resume()

    async def restart(self) -> None:
        """Restart this lane's flow."""
        self.remove_class("done")
        track = self.track
        if track is not None:
            await track.restart()

    def _on_track_finished(self) -> None:
        self.add_class("done")
        self.post_message(self.Finished())
