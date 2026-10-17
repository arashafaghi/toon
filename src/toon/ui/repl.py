"""Interactive REPL widget: echoed input, output log, and command dispatch.

The host owns the REPL lifetime and mounts it on the base screen. The REPL
never reaches into the application object: navigation and output clearing are
requested through :class:`toon.api.ViewHost`, which command handlers receive via
their ``CommandContext``. ``Escape``-to-go-back is handled by the app.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Input, RichLog

from toon.api import ViewHost
from toon.runtime.dispatcher import Dispatcher


class Repl(Vertical):
    """Input/output pane that dispatches every submitted line."""

    def __init__(
        self,
        dispatcher: Dispatcher,
        host: ViewHost,
        *,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self.dispatcher = dispatcher
        self.host = host
        self._log: RichLog | None = None
        self._input: Input | None = None

    def compose(self) -> ComposeResult:
        self._log = RichLog(
            id="repl-log",
            wrap=True,
            highlight=False,
            markup=True,
            min_width=1,
        )
        self._input = Input(
            placeholder="Type a command and press Enter (try 'help')",
            id="repl-input",
        )
        yield self._log
        yield self._input

    def on_mount(self) -> None:
        """Give the input focus as soon as the REPL is mounted."""
        if self._input is not None:
            self._input.focus()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Echo the line, dispatch it, render the result, and refocus."""
        line = event.value
        event.input.value = ""

        if line.strip() == "":
            return

        self._write(f"> {line}")

        result = await self.dispatcher.dispatch(line, host=self.host)

        if result.error is not None:
            self._write(f"[red]{result.error}[/red]")
        elif result.output:
            self._write(result.output)

        event.input.focus()

    def clear_output(self) -> None:
        """Clear the REPL output log."""
        if self._log is not None:
            self._log.clear()

    def _write(self, text: str) -> None:
        """Append ``text`` to the output log when it is available."""
        if self._log is not None:
            self._log.write(text)
