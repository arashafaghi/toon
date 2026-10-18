"""Behavior tests for the REPL: dispatch, output, and error handling.

The REPL is exercised through the real ``Input`` submit path, so these tests
cover the same flow a user triggers by typing a line and pressing Enter.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from textual.pilot import Pilot

from toon.api import Command, CommandContext
from toon.app import ToonApp

ReadRepl = Callable[[ToonApp], str]
SubmitLine = Callable[[ToonApp, Pilot[None], str], Awaitable[None]]


def _explode(ctx: CommandContext) -> str:
    """A handler that always raises, to prove errors are contained."""
    raise ValueError("boom")


async def test_submitting_a_command_shows_its_output(
    app: ToonApp, read_repl: ReadRepl, submit: SubmitLine
) -> None:
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()

        await submit(app, pilot, "echo hello world")

        text = read_repl(app)
        assert "> echo hello world" in text
        assert "hello world" in text


async def test_blank_and_whitespace_input_is_a_noop(
    app: ToonApp, read_repl: ReadRepl, submit: SubmitLine
) -> None:
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        before = read_repl(app)

        await submit(app, pilot, "")
        await submit(app, pilot, "    ")

        assert read_repl(app) == before


async def test_unknown_command_reports_an_error_and_keeps_working(
    app: ToonApp, read_repl: ReadRepl, submit: SubmitLine
) -> None:
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()

        await submit(app, pilot, "no_such_command_here")

        text = read_repl(app)
        assert "Unknown command 'no_such_command_here'." in text
        assert "help" in text

        # The REPL is still usable after the error.
        await submit(app, pilot, "echo recovered")
        assert "recovered" in read_repl(app)


async def test_raising_handler_shows_the_error(
    app: ToonApp, read_repl: ReadRepl, submit: SubmitLine
) -> None:
    app.registry.register_command(Command("explode", _explode, "Always raises."))

    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()

        await submit(app, pilot, "explode")

        text = read_repl(app)
        assert "ValueError: boom" in text

        # A handler failure must not take the app down.
        await submit(app, pilot, "echo alive")
        assert "alive" in read_repl(app)


async def test_repl_handles_several_commands_in_sequence(
    app: ToonApp, read_repl: ReadRepl, submit: SubmitLine
) -> None:
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()

        for line in ("echo one", "echo two", "echo three"):
            await submit(app, pilot, line)

        text = read_repl(app)
        assert text.index("one") < text.index("two") < text.index("three")
        for line in ("> echo one", "> echo two", "> echo three"):
            assert line in text
