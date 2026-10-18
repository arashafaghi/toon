"""Graph demo plugin: a pipeline of nodes wired with travelling flow pulses.

Recreates the "flow graph" animation: dim dashed **wires** between node boxes
with a bright **pulse** travelling along each one, one-way and repeating, while
node borders light up as the pipeline advances
(``scan -> edit -> verify -> sign-off``).

It uses only the public API — ``FlowEdge`` (from ``toon.api``) for the wires and
plain ``Static`` boxes for the nodes.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Static

from toon.api import Command, CommandContext, ExtensionRegistry, FlowEdge

WIDGET_NAME = "graph_demo"

#: Seconds for a pulse to cross a wire.
EDGE_SECONDS = 1.3
#: Rows in each vertical wire.
EDGE_LENGTH = 4
#: Trailing dots behind each pulse.
EDGE_TRAIL = 2
#: Seconds between node state changes.
STAGE_SECONDS = 1.6

_STAGES = ("scan", "edit", "verify")


class GraphDemoWidget(Vertical):
    """Widget contribution: nodes wired with animated flow pulses."""

    DEFAULT_CSS = """
    GraphDemoWidget {
        height: auto;
        padding: 1 2;
        align-horizontal: center;
    }
    GraphDemoWidget .node {
        width: auto;
        height: 3;
        padding: 0 2;
        content-align: center middle;
        border: round #30363d;
        background: #161b22;
        color: #c9d1d9;
    }
    GraphDemoWidget .node.active {
        border: round #d29922;
        color: #d29922;
        text-style: bold;
    }
    GraphDemoWidget .node.done {
        border: round #3fb950;
        background: #0f2a17;
        color: #3fb950;
        text-style: bold;
    }
    GraphDemoWidget #stages {
        width: auto;
        height: auto;
    }
    GraphDemoWidget .stage-col {
        width: auto;
        height: auto;
        align-horizontal: center;
        margin: 0 3;
    }
    GraphDemoWidget FlowEdge {
        color: #58a6ff;
    }
    GraphDemoWidget #graph-status {
        height: 1;
        margin-top: 1;
        color: #8b949e;
    }
    GraphDemoWidget #graph-buttons {
        width: auto;
        height: auto;
        margin-top: 1;
    }
    GraphDemoWidget #graph-buttons Button {
        margin-right: 1;
    }
    """

    def compose(self) -> ComposeResult:
        """Lay out the pipeline: Opus -> fork -> stages -> sign-off."""
        yield Static("OPUS · orchestrator", classes="node", id="node-opus")
        yield FlowEdge(
            orientation="vertical",
            length=EDGE_LENGTH,
            duration=EDGE_SECONDS,
            trail_length=EDGE_TRAIL,
        )
        yield Static("FORK · routing", classes="node", id="node-fork")
        with Horizontal(id="stages"):
            for name in _STAGES:
                with Vertical(classes="stage-col"):
                    yield FlowEdge(
                        orientation="vertical",
                        length=EDGE_LENGTH,
                        duration=EDGE_SECONDS,
                        trail_length=EDGE_TRAIL,
                    )
                    yield Static(name, classes="node", id=f"node-{name}")
        yield FlowEdge(
            orientation="vertical",
            length=EDGE_LENGTH,
            duration=EDGE_SECONDS,
            trail_length=EDGE_TRAIL,
        )
        yield Static("SIGN-OFF · verified only", classes="node", id="node-signoff")
        yield Static("Running", id="graph-status")
        with Horizontal(id="graph-buttons"):
            yield Button("Pause", id="graph-toggle", variant="warning")
            yield Button("Restart", id="graph-restart")

    def on_mount(self) -> None:
        """Start the wires (they self-start) and the stage cycling."""
        self._paused = False
        self._stage = 0
        self._apply_stage()
        self.set_interval(STAGE_SECONDS, self._advance)

    # --- stage state -------------------------------------------------------

    def _apply_stage(self) -> None:
        for index, name in enumerate(_STAGES):
            node = self.query_one(f"#node-{name}", Static)
            node.set_class(index < self._stage, "done")
            node.set_class(index == self._stage, "active")
        self.query_one("#node-signoff", Static).set_class(self._stage >= len(_STAGES), "active")

    def _advance(self) -> None:
        if self._paused:
            return
        self._stage = (self._stage + 1) % (len(_STAGES) + 1)
        self._apply_stage()

    # --- controls ----------------------------------------------------------

    def _edges(self) -> list[FlowEdge]:
        return list(self.query(FlowEdge))

    def _toggle(self) -> Button:
        return self.query_one("#graph-toggle", Button)

    def _set_status(self, text: str) -> None:
        self.query_one("#graph-status", Static).update(text)

    async def _on_toggle(self) -> None:
        if self._paused:
            self._paused = False
            for edge in self._edges():
                edge.resume()
            self._toggle().label = "Pause"
            self._set_status("Running")
        else:
            self._paused = True
            for edge in self._edges():
                await edge.pause()
            self._toggle().label = "Resume"
            self._set_status("Paused")

    async def _on_restart(self) -> None:
        self._paused = False
        toggle = self._toggle()
        toggle.disabled = False
        toggle.label = "Pause"
        self._set_status("Running")
        self._stage = 0
        for name in _STAGES:
            self.query_one(f"#node-{name}", Static).remove_class("done", "active")
        self.query_one("#node-signoff", Static).remove_class("active")
        self._apply_stage()
        for edge in self._edges():
            await edge.restart()

    async def on_unmount(self) -> None:
        """Stop the wires when the widget is removed."""
        for edge in self._edges():
            await edge.pause()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Route the two buttons to their actions."""
        event.stop()
        if event.button.id == "graph-toggle":
            await self._on_toggle()
        elif event.button.id == "graph-restart":
            await self._on_restart()


def make_graph_demo() -> GraphDemoWidget:
    """Return a *fresh* widget instance on every call."""
    return GraphDemoWidget()


def show_graph_demo(ctx: CommandContext) -> str:
    """Mount the graph demo widget in the host content area."""
    ctx.host.open_view(WIDGET_NAME)
    return "Opened the graph demo: nodes wired with travelling flow pulses."


def register(registry: ExtensionRegistry) -> None:
    """Register the widget and the command that opens it."""
    registry.register_widget(
        WIDGET_NAME,
        make_graph_demo,
        description="Pipeline of nodes wired with animated flow pulses.",
        title="Graph",
    )
    registry.register_command(
        Command("graph_demo", show_graph_demo, "Open the animated flow-graph demo.")
    )
