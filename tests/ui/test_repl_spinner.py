"""Behavior tests for the REPL's in-progress spinner."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable

from textual.pilot import Pilot

from toon.api import Command, CommandContext
from toon.api.widgets import Spinner
from toon.app import ToonApp
from toon.ui.repl import Repl

ReadRepl = Callable[[ToonApp], str]


async def _wait_until(
    pilot: Pilot[None], predicate: Callable[[], bool], *, timeout: float = 3.0
) -> None:
    """Poll ``predicate`` while letting the app process timers."""
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > deadline:
            raise AssertionError("condition was not met before the timeout")
        await pilot.pause(0.01)


async def test_async_command_shows_a_spinner_until_it_finishes(
    app: ToonApp, read_repl: ReadRepl
) -> None:
    gate = asyncio.Event()

    async def slow(ctx: CommandContext) -> str:
        await gate.wait()
        return "done"

    app.registry.register_command(Command("slow", slow, "Wait for the gate."))

    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        repl = app.query_one(Repl)
        spinner = repl.query_one(Spinner)
        assert spinner.has_class("hidden")

        task = asyncio.create_task(repl.run("slow"))
        try:
            await _wait_until(pilot, lambda: spinner.is_spinning)
        finally:
            gate.set()
        await task
        await pilot.pause()

        assert spinner.is_spinning is False
        assert spinner.has_class("hidden")
        assert "done" in read_repl(app)


async def test_spinner_hides_when_the_command_fails(app: ToonApp, read_repl: ReadRepl) -> None:
    gate = asyncio.Event()

    async def failing(ctx: CommandContext) -> str:
        await gate.wait()
        raise RuntimeError("nope")

    app.registry.register_command(Command("failing", failing, "Wait, then fail."))

    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        repl = app.query_one(Repl)
        spinner = repl.query_one(Spinner)

        task = asyncio.create_task(repl.run("failing"))
        try:
            await _wait_until(pilot, lambda: spinner.is_spinning)
        finally:
            gate.set()
        await task
        await pilot.pause()

        assert spinner.is_spinning is False
        assert spinner.has_class("hidden")
        assert "RuntimeError: nope" in read_repl(app)
