"""Interactive REPL widget: echoed input, output log, and command dispatch.

The host owns the REPL lifetime and mounts it on the base screen. The REPL
never reaches into the application object: navigation and output clearing are
requested through :class:`toon.api.ViewHost`, which command handlers receive via
their ``CommandContext``. ``Escape``-to-go-back is handled by the app.

The input keeps a command history (persisted by the host). ``Up``/``Down`` walk
the history with **prefix matching** — like bash's ``history-search-backward`` /
``history-search-forward`` — so typing ``gh`` then ``Up`` cycles only through
past commands starting with ``gh``.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Input, RichLog

from toon.api import ViewHost
from toon.runtime.dispatcher import Dispatcher

#: How many recent commands to remember.
MAX_HISTORY = 20


class Repl(Vertical):
    """Input/output pane that dispatches every submitted line."""

    BINDINGS = [
        Binding("up", "history_previous", "History", show=False),
        Binding("down", "history_next", "History", show=False),
    ]

    def __init__(
        self,
        dispatcher: Dispatcher,
        host: ViewHost,
        *,
        history: Sequence[str] = (),
        on_history_changed: Callable[[list[str]], None] | None = None,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self.dispatcher = dispatcher
        self.host = host
        self._log: RichLog | None = None
        self._input: Input | None = None
        self._history: list[str] = list(history)
        self._on_history_changed = on_history_changed
        self._hist_index: int | None = None
        self._hist_prefix = ""

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
        """Record the line, dispatch it, and refocus the input."""
        line = event.value
        event.input.value = ""
        self._hist_index = None
        self._record(line)
        await self.run(line)
        event.input.focus()

    async def run(self, line: str) -> None:
        """Echo ``line``, dispatch it, and render the result.

        Shared by the REPL input and the command palette so both paths behave
        identically. Blank input does nothing.
        """
        if line.strip() == "":
            return

        self._write(f"> {line}")

        result = await self.dispatcher.dispatch(line, host=self.host)

        if result.error is not None:
            self._write(f"[red]{result.error}[/red]")
        elif result.output:
            self._write(result.output)

    def clear_output(self) -> None:
        """Clear the REPL output log."""
        if self._log is not None:
            self._log.clear()

    def write_output(self, text: str) -> None:
        """Append ``text`` to the output log (public entry point for the host)."""
        self._write(text)

    # --- history -----------------------------------------------------------

    def action_history_previous(self) -> None:
        """Move to the previous history entry matching the current prefix."""
        self._search_history(-1)

    def action_history_next(self) -> None:
        """Move to the next history entry matching the current prefix."""
        self._search_history(1)

    def _record(self, line: str) -> None:
        if not line.strip() or (self._history and self._history[-1] == line):
            return
        self._history.append(line)
        del self._history[:-MAX_HISTORY]
        if self._on_history_changed is not None:
            self._on_history_changed(list(self._history))

    def _search_history(self, step: int) -> None:
        field = self._input
        if field is None or not self._history:
            return
        if self._hist_index is None:
            if step > 0:
                return  # nothing to move forward to yet
            self._hist_prefix = field.value
            self._hist_index = len(self._history)

        index = self._hist_index + step
        while 0 <= index < len(self._history):
            if self._history[index].startswith(self._hist_prefix):
                self._hist_index = index
                self._set_input(self._history[index])
                return
            index += step

        if step > 0:  # walked past the newest match: restore the draft
            self._hist_index = None
            self._set_input(self._hist_prefix)

    def _set_input(self, text: str) -> None:
        field = self._input
        if field is None:
            return
        field.value = text
        field.cursor_position = len(text)

    def _write(self, text: str) -> None:
        """Append ``text`` to the output log when it is available."""
        if self._log is not None:
            self._log.write(text)
