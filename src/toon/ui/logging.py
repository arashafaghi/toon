"""Bridge Loguru output into the REPL output area.

:func:`install_logging` repoints Loguru's global logger at a
:class:`ReplLogSink`, dropping Loguru's default stderr sink, so every record
emitted anywhere in-process -- host logic *and* plugin code (``from toon.api
import logger``) -- is written into the REPL's ``RichLog``.

Records emitted before the REPL is mounted are common: plugins are imported and
registered during ``ToonApp.__init__``. Those records are buffered and flushed
when :meth:`ReplLogSink.attach` is called from ``on_mount``. Records emitted from
a non-UI thread are marshalled back onto the UI thread.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any

from loguru import logger
from rich.markup import escape

if TYPE_CHECKING:
    from loguru import Message
    from textual.app import App

    from toon.ui.repl import Repl

__all__ = ["LOG_FORMAT", "LOG_LEVEL", "ReplLogSink", "install_logging"]

#: Loguru's default line content (time, level, source location, message).
LOG_FORMAT = "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}"

#: Minimum level captured by the REPL sink.
LOG_LEVEL = "DEBUG"

#: Rich styles used to colour a whole line by level (empty means "leave plain").
_LEVEL_STYLES: dict[str, str] = {
    "TRACE": "dim",
    "DEBUG": "dim",
    "INFO": "",
    "SUCCESS": "green",
    "WARNING": "yellow",
    "ERROR": "red",
    "CRITICAL": "bold red",
}


class ReplLogSink:
    """A Loguru sink that renders records into the REPL output area."""

    def __init__(self, app: App[Any]) -> None:
        self._app = app
        self._repl: Repl | None = None
        self._buffer: list[str] = []

    def __call__(self, message: Message) -> None:
        """Render one record, buffering it until the REPL is available."""
        line = self._render(message)
        if self._repl is None:
            self._buffer.append(line)
        else:
            self._deliver(line)

    def attach(self, repl: Repl) -> None:
        """Bind the sink to ``repl`` and flush anything buffered so far."""
        self._repl = repl
        pending, self._buffer = self._buffer, []
        for line in pending:
            repl.write_output(line)

    def _render(self, message: Message) -> str:
        """Format a record as one escaped, level-coloured line."""
        text = escape(str(message).rstrip("\n"))
        style = _LEVEL_STYLES.get(message.record["level"].name, "")
        return f"[{style}]{text}[/{style}]" if style else text

    def _deliver(self, line: str) -> None:
        """Write ``line`` on the UI thread, from whichever thread we're on."""
        repl = self._repl
        if repl is None:
            return
        try:
            if threading.current_thread() is threading.main_thread():
                repl.write_output(line)
            else:
                self._app.call_from_thread(repl.write_output, line)
        except Exception:  # Logging must never take down the app.
            pass


def install_logging(app: App[Any]) -> ReplLogSink:
    """Point Loguru's global logger at a REPL sink and return it."""
    sink = ReplLogSink(app)
    logger.remove()
    logger.add(sink, format=LOG_FORMAT, colorize=False, level=LOG_LEVEL)
    return sink
