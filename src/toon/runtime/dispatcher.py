"""Turn a raw REPL line into a :class:`~toon.api.CommandResult`.

The dispatcher owns tokenization (``shlex``, no shell features), command
lookup, and handler invocation. It normalises sync and async handlers and
guarantees that it never raises: every failure becomes an ``error`` result the
REPL can display.
"""

from __future__ import annotations

import inspect
import shlex

from toon.api import CommandContext, CommandResult, ViewHost
from toon.runtime.registry import Registry

__all__ = ["Dispatcher"]


class Dispatcher:
    """Resolve commands from ``registry`` and execute them safely."""

    def __init__(self, registry: Registry) -> None:
        self._registry = registry

    async def dispatch(self, line: str, *, host: ViewHost) -> CommandResult:
        """Parse and run ``line``, always returning a result (never raising)."""
        if line.strip() == "":
            return CommandResult(command="")

        try:
            tokens = shlex.split(line)
        except ValueError as exc:
            return CommandResult(command="", error=f"Could not parse input: {exc}")

        if not tokens:
            return CommandResult(command="")

        name, *rest = tokens
        command = self._registry.get_command(name)
        if command is None:
            return CommandResult(
                command=name,
                error=f"Unknown command '{name}'. Type 'help' for available commands.",
            )

        context = CommandContext(args=tuple(rest), host=host)
        try:
            result = command.handler(context)
            if inspect.isawaitable(result):
                result = await result
        except Exception as exc:  # Handlers are untrusted; report, never propagate.
            return CommandResult(command=name, error=f"{type(exc).__name__}: {exc}")

        return CommandResult(command=name, output="" if result is None else str(result))
