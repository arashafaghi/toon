"""Behavior of the dispatcher: parsing, lookup, and safe handler execution."""

from __future__ import annotations

from typing import Any

import pytest

from toon.api import Command, CommandContext, CommandResult
from toon.runtime.dispatcher import Dispatcher
from toon.runtime.registry import Registry


def _dispatcher(*commands: Command) -> Dispatcher:
    registry = Registry()
    for command in commands:
        registry.register_command(command)
    return Dispatcher(registry)


@pytest.mark.parametrize("line", ["", "   ", "\t\n  "])
async def test_empty_input_does_nothing(line: str, view_host: Any) -> None:
    dispatcher = _dispatcher()

    result = await dispatcher.dispatch(line, host=view_host)

    assert result == CommandResult(command="")
    assert result.ok is True


async def test_unknown_command_returns_error_without_raising(
    view_host: Any,
) -> None:
    dispatcher = _dispatcher()

    result = await dispatcher.dispatch("nope", host=view_host)

    assert result.ok is False
    assert result.command == "nope"
    assert "Unknown command 'nope'" in (result.error or "")


async def test_sync_handler_receives_shlex_split_arguments(
    view_host: Any,
) -> None:
    dispatcher = _dispatcher(Command("echo", lambda ctx: "|".join(ctx.args)))

    result = await dispatcher.dispatch("echo \"hello world\" 'a b' plain", host=view_host)

    assert result.ok is True
    assert result.output == "hello world|a b|plain"


async def test_async_handler_is_awaited(view_host: Any) -> None:
    async def handler(ctx: CommandContext) -> str:
        return f"async {ctx.args[0]}"

    dispatcher = _dispatcher(Command("go", handler))

    result = await dispatcher.dispatch("go fast", host=view_host)

    assert result == CommandResult(command="go", output="async fast")


async def test_none_result_becomes_empty_output(view_host: Any) -> None:
    dispatcher = _dispatcher(Command("noop", lambda ctx: None))

    result = await dispatcher.dispatch("noop", host=view_host)

    assert result.ok is True
    assert result.output == ""


async def test_non_string_result_is_stringified(view_host: Any) -> None:
    dispatcher = _dispatcher(Command("count", lambda ctx: 42))

    result = await dispatcher.dispatch("count", host=view_host)

    assert result.output == "42"


async def test_handler_exception_is_reported_as_error(
    view_host: Any,
) -> None:
    def explode(ctx: CommandContext) -> str:
        raise ValueError("boom")

    dispatcher = _dispatcher(Command("bad", explode))

    result = await dispatcher.dispatch("bad", host=view_host)

    assert result.ok is False
    assert result.command == "bad"
    assert result.error == "ValueError: boom"


async def test_async_handler_exception_is_reported_as_error(
    view_host: Any,
) -> None:
    async def explode(ctx: CommandContext) -> str:
        raise RuntimeError("async boom")

    dispatcher = _dispatcher(Command("bad", explode))

    result = await dispatcher.dispatch("bad", host=view_host)

    assert result.ok is False
    assert result.error == "RuntimeError: async boom"


async def test_unparseable_quoting_returns_error(view_host: Any) -> None:
    dispatcher = _dispatcher(Command("echo", lambda ctx: " ".join(ctx.args)))

    result = await dispatcher.dispatch('echo "unterminated', host=view_host)

    assert result.ok is False
    assert (result.error or "").startswith("Could not parse input:")


async def test_handler_receives_the_injected_host(view_host: Any) -> None:
    seen: list[CommandContext] = []

    def capture(ctx: CommandContext) -> None:
        seen.append(ctx)

    dispatcher = _dispatcher(Command("capture", capture))

    await dispatcher.dispatch("capture a b", host=view_host)

    assert seen[0].host is view_host
    assert seen[0].args == ("a", "b")
