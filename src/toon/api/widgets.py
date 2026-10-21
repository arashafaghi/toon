"""Reusable Textual widgets for plugin UI contributions.

This is the UI-facing half of the public extension API. Plugins import from here
to build an animated flow without re-implementing the animation machinery::

    from toon.api import FlowLane          # lazy re-export
    from toon.api.widgets import FlowTrack # or import the module directly

The track draws a single arrow that travels horizontally; the travel can be
``"ping-pong"`` (reverse at each end) or ``"one-way"`` (loop back to the start).

Importing this module pulls in Textual. ``toon.api`` itself stays Textual-free
at runtime -- it exposes these names lazily so the core runtime never imports
Textual.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Sequence
from typing import Any, Literal, TypedDict

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.reactive import reactive
from textual.timer import Timer
from textual.widgets import Static

__all__ = [
    "DEFAULT_SPINNER_PRESET",
    "FlowEdge",
    "FlowLane",
    "FlowMode",
    "FlowTrack",
    "SPINNER_FRAMES",
    "SPINNER_PRESETS",
    "SPINNER_RANDOM_PRESETS",
    "Spinner",
    "render_edge",
    "render_track",
]

#: Busy-spinner presets. Each value is a sequence of one-cell frames.
#:
#: ``dot_cycle`` is the default: eight braille dots arranged as a rotating
#: spinner. ``braille_random`` covers the whole braille block and is animated
#: randomly (see :data:`SPINNER_RANDOM_PRESETS`).
SPINNER_PRESETS: dict[str, tuple[str, ...]] = {
    "dot_cycle": ("⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷"),
    "braille_random": tuple(chr(codepoint) for codepoint in range(0x2800, 0x2900)),
    "z_arrow": ("←", "↖", "↑", "↗", "→", "↘", "↓", "↙"),
    "z_b": ("b", "ᓂ", "q", "ᓄ"),
    "z_d": ("d", "ᓇ", "p", "ᓀ"),
    "z_bar": ("|", "/", "—", "\\"),
    "z_x": ("x", "+"),
    "z_1": ("◰", "◳", "◲", "◱"),
    "z_2": ("◴", "◷", "◶", "◵"),
    "z_3": ("◐", "◓", "◑", "◒"),
    "y_d": ("d", "|", "b", "|"),
    "y_q": ("q", "|", "p", "|"),
    "x_b": ("ᓂ", "—", "ᓄ", "—"),
    "x_d": ("ᓇ", "—", "ᓀ", "—"),
    "grow_a": ("|", "b", "O", "b"),
    "grow_b": ("_", "o", "O", "o"),
    "grow_c": (".", "o", "O", "@", "*", " "),
    "grow_d": ("▁", "▃", "▄", "▅", "▆", "▇", "█", "▇", "▆", "▅", "▄", "▃"),
    "grow_e": (
        "▉",
        "▊",
        "▋",
        "▌",
        "▍",
        "▎",
        "▏",
        "▎",
        "▍",
        "▌",
        "▋",
        "▊",
        "▉",
    ),
}

#: Preset used when :class:`Spinner` is constructed without ``frames``/``preset``.
DEFAULT_SPINNER_PRESET = "dot_cycle"

#: Default spinner frames (the rotating braille dots).
SPINNER_FRAMES: tuple[str, ...] = SPINNER_PRESETS[DEFAULT_SPINNER_PRESET]

#: Presets whose frames are chosen randomly instead of in sequence.
SPINNER_RANDOM_PRESETS: frozenset[str] = frozenset({"braille_random"})


#: ``"ping-pong"`` reverses at each end; ``"one-way"`` loops back to the start.
FlowMode = Literal["ping-pong", "one-way"]

#: Axis a flow edge runs along.
_Orientation = Literal["horizontal", "vertical"]

_DOTS = "·"


class _TrackConfig(TypedDict):
    """Keyword arguments :class:`FlowLane` forwards to its :class:`FlowTrack`."""

    length: int
    mode: FlowMode
    duration: float
    traversals: int


def render_track(phase: float, direction: int, length: int) -> str:
    """Render one horizontal flow-track frame: a single arrow among dots.

    Args:
        phase: Fractional progress, ``0.0`` (start) to ``1.0`` (end).
        direction: Positive points right (``▶``), negative points left (``◀``).
        length: Number of cells in the track.

    Returns:
        The track as a single line of text.
    """
    position = min(1.0, max(0.0, phase)) * (length - 1)
    head = min(length - 1, max(0, int(position)))
    arrow = "▶" if direction >= 0 else "◀"
    return _DOTS * head + arrow + _DOTS * (length - 1 - head)


class FlowTrack(Static):
    """A track with an animated arrow that travels along it.

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
        mode: FlowMode = "ping-pong",
        duration: float = 1.4,
        traversals: int = 3,
        easing: str = "linear",
        **kwargs: Any,
    ) -> None:
        super().__init__("", **kwargs)
        self._length = max(2, length)
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
        """Freeze the arrow where it is."""
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
        text = render_track(self.phase, self.direction, self._length)
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
        mode: FlowMode = "ping-pong",
        duration: float = 1.4,
        traversals: int = 3,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._label = label
        self._source = source
        self._sink = sink
        self._track_config: _TrackConfig = {
            "length": length,
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


# --- flow edges (wire + travelling glow) -----------------------------------

_EDGE_WIRE = "┄"
_EDGE_WIRE_VERTICAL = "┆"
_EDGE_PACKET = "●"
_EDGE_TRAIL = "·"


def render_edge(
    phase: float,
    length: int,
    *,
    orientation: _Orientation = "horizontal",
    direction: int = 1,
    wire: str = _EDGE_WIRE,
    packet: str = _EDGE_PACKET,
    trail: str = _EDGE_TRAIL,
    trail_length: int = 3,
) -> str:
    """Render one edge frame: a wire with a glow travelling along it.

    ``phase`` runs ``0.0`` (wire start) to ``1.0`` (wire end); ``direction`` is
    positive for right/down, negative for left/up. Returns a single line, or one
    line per cell when ``orientation == "vertical"``.
    """
    length = max(2, length)
    position = min(1.0, max(0.0, phase)) * (length - 1)
    head = min(length - 1, max(0, int(round(position))))

    cells = [wire] * length
    cells[head] = packet

    step = -1 if direction >= 0 else 1  # walk backwards along the flow
    for offset in range(1, trail_length + 1):
        index = head + step * offset
        if 0 <= index < length:
            cells[index] = trail

    return "\n".join(cells) if orientation == "vertical" else "".join(cells)


class FlowEdge(Static):
    """A wire (dashed line) with a glowing pulse travelling along it, one-way.

    Like a data packet on a cable: the pulse starts at one end, runs to the
    other, and repeats. Reusable across plugins; it owns the animation
    (:meth:`start` / :meth:`pause` / :meth:`resume` / :meth:`restart`), repaints
    only when the frame changes, and calls ``on_finished`` once if a finite
    ``traversals`` count is given (by default it loops forever).
    """

    DEFAULT_CSS = """
    FlowEdge {
        width: auto;
        height: auto;
        color: #58a6ff;
    }
    FlowEdge.done {
        color: #3fb950;
    }
    """

    phase = reactive(0.0, layout=False)

    def __init__(
        self,
        *,
        length: int = 24,
        orientation: _Orientation = "horizontal",
        direction: int = 1,
        duration: float = 1.2,
        traversals: int | None = None,
        wire: str | None = None,
        packet: str = _EDGE_PACKET,
        trail: str = _EDGE_TRAIL,
        trail_length: int = 3,
        easing: str = "linear",
        **kwargs: Any,
    ) -> None:
        super().__init__("", **kwargs)
        self._length = max(2, length)
        self._orientation = orientation
        self._direction = direction
        self._duration = duration
        self._traversals = traversals
        self._wire = (
            wire
            if wire is not None
            else (_EDGE_WIRE_VERTICAL if orientation == "vertical" else _EDGE_WIRE)
        )
        self._packet = packet
        self._trail = trail
        self._trail_length = max(0, trail_length)
        self._easing = easing
        self._count = 0
        self._is_running = False
        self._done = False
        self._last = ""
        self.on_finished: Callable[[], None] | None = None

    # --- lifecycle ---------------------------------------------------------

    def on_mount(self) -> None:
        """Render the first frame and start flowing."""
        self._repaint()
        self.start()

    def watch_phase(self, _value: float) -> None:
        """Re-render whenever the animation advances the phase."""
        self._repaint()

    @property
    def is_done(self) -> bool:
        """Whether a finite edge has finished all its traversals."""
        return self._done

    # --- control -----------------------------------------------------------

    def start(self) -> None:
        """Reset to the start and flow."""
        self.remove_class("done")
        self._count = 0
        self._done = False
        self._is_running = True
        self.phase = 0.0
        self._run(self._duration)

    async def pause(self) -> None:
        """Freeze the pulse where it is."""
        self._is_running = False
        await self.stop_animation("phase", complete=False)

    def resume(self) -> None:
        """Continue to the end over the remaining time."""
        self._is_running = True
        remaining = max(0.05, self._duration * (1.0 - self.phase))
        self._run(remaining)

    async def restart(self) -> None:
        """Stop and start over."""
        await self.stop_animation("phase", complete=False)
        self.start()

    def _run(self, duration: float) -> None:
        self.animate(
            "phase",
            1.0,
            duration=duration,
            easing=self._easing,
            on_complete=self._on_complete,
        )

    def _on_complete(self) -> None:
        if not self._is_running:
            return
        self._count += 1
        if self._traversals is not None and self._count >= self._traversals:
            self._finish()
            return
        self.phase = 0.0
        self._run(self._duration)

    def _finish(self) -> None:
        self._is_running = False
        self._done = True
        self.add_class("done")
        if self.on_finished is not None:
            self.on_finished()

    async def on_unmount(self) -> None:
        """Stop any in-flight animation when the edge is removed."""
        await self.stop_animation("phase", complete=False)

    # --- rendering ---------------------------------------------------------

    def _repaint(self) -> None:
        text = render_edge(
            self.phase,
            self._length,
            orientation=self._orientation,
            direction=self._direction,
            wire=self._wire,
            packet=self._packet,
            trail=self._trail,
            trail_length=self._trail_length,
        )
        if text != self._last:  # only touch the DOM when the frame changes
            self._last = text
            # Emphasise the packet so the glow reads on a dim wire.
            self.update(text.replace(self._packet, f"[bold]{self._packet}[/]", 1))


# --- busy spinner -----------------------------------------------------------


def _frames_for_preset(preset: str) -> tuple[str, ...]:
    """Return a preset's frames, raising a helpful error for unknown names."""
    try:
        return SPINNER_PRESETS[preset]
    except KeyError:
        choices = ", ".join(SPINNER_PRESETS)
        raise ValueError(f"unknown spinner preset {preset!r}; choose from: {choices}") from None


class Spinner(Static):
    """A one-line busy indicator with Unicode and ASCII presets.

    The default preset is a rotating braille spinner (``⣾⣽⣻⢿⡿⣟⣯⣷``),
    one frame every 120 ms. Pick a built-in preset with ``preset=``, pass custom
    ``frames=``, or switch presets at runtime with :meth:`set_preset`::

        spinner = Spinner(preset="z_arrow")
        spinner.start("Fetching builds...")
        ...
        spinner.stop()

    ``preset="braille_random"`` chooses a random character from the whole
    braille block on every tick. See :data:`SPINNER_PRESETS` for all presets.
    """

    DEFAULT_CSS = """
    Spinner {
        height: 1;
        width: auto;
    }
    Spinner.hidden {
        display: none;
    }
    """

    def __init__(
        self,
        *,
        frames: Sequence[str] | None = None,
        preset: str | None = None,
        interval: float = 0.12,
        label: str = "",
        autostart: bool = False,
        randomize: bool | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__("", markup=False, **kwargs)
        if preset is not None and frames is not None:
            raise ValueError("pass either preset= or frames=, not both")

        if preset is not None:
            self._preset: str | None = preset
            self._frames = _frames_for_preset(preset)
            self._randomize = preset in SPINNER_RANDOM_PRESETS if randomize is None else randomize
        else:
            custom = tuple(frames) if frames is not None else SPINNER_FRAMES
            if not custom:
                raise ValueError("frames must not be empty")
            self._preset = None
            self._frames = custom
            self._randomize = bool(randomize)

        self._interval = interval
        self._label = label
        self._autostart = autostart
        self._index = 0
        self._timer: Timer | None = None
        self.add_class("hidden")

    # --- lifecycle ---------------------------------------------------------

    def on_mount(self) -> None:
        """Render the first frame, and start immediately if requested."""
        self._paint()
        if self._autostart:
            self.start()

    def on_unmount(self) -> None:
        """Stop the timer so it cannot outlive the widget."""
        if self._timer is not None:
            self._timer.stop()
            self._timer = None

    # --- control -----------------------------------------------------------

    @property
    def is_spinning(self) -> bool:
        """Whether the spinner is currently animating."""
        return self._timer is not None

    @property
    def label(self) -> str:
        """Text shown after the spinning frame."""
        return self._label

    @label.setter
    def label(self, value: str) -> None:
        self._label = value
        self._paint()

    @property
    def preset(self) -> str | None:
        """Selected preset name, or ``None`` when using custom frames."""
        return self._preset

    @preset.setter
    def preset(self, value: str) -> None:
        self.set_preset(value)

    @property
    def frames(self) -> tuple[str, ...]:
        """The frame sequence currently in use."""
        return self._frames

    @property
    def randomize(self) -> bool:
        """Whether a random frame is chosen on each tick."""
        return self._randomize

    @randomize.setter
    def randomize(self, value: bool) -> None:
        self._randomize = value

    def set_preset(self, preset: str) -> None:
        """Switch to a built-in preset and reset to its first frame."""
        frames = _frames_for_preset(preset)
        self._preset = preset
        self._frames = frames
        self._randomize = preset in SPINNER_RANDOM_PRESETS
        self._index = 0
        self._paint()

    def start(self, label: str | None = None) -> None:
        """Show the spinner and start (or restart) animating."""
        if label is not None:
            self._label = label
        self._index = 0
        self.remove_class("hidden")
        self._paint()
        if self._timer is None:
            self._timer = self.set_interval(self._interval, self._tick)

    def stop(self, *, hide: bool = True) -> None:
        """Stop animating, optionally hiding the widget (the default)."""
        if self._timer is not None:
            self._timer.stop()
            self._timer = None
        if hide:
            self.add_class("hidden")

    # --- rendering ---------------------------------------------------------

    def _tick(self) -> None:
        if self._randomize:
            self._index = random.randrange(len(self._frames))
        else:
            self._index = (self._index + 1) % len(self._frames)
        self._paint()

    def _paint(self) -> None:
        frame = self._frames[self._index]
        self.update(f"{frame} {self._label}".rstrip())
