"""Behavior tests for the host application skeleton.

These tests drive the real :class:`toon.app.ToonApp` through Textual's headless
pilot and assert on what a user would observe: the mounted widgets, the header
text, and the REPL output.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from textual.pilot import Pilot
from textual.widgets import Static

from toon.app import ToonApp
from toon.ui.content import ContentArea
from toon.ui.footer import AppFooter
from toon.ui.header import AppHeader
from toon.ui.repl import Repl

ReadRepl = Callable[[ToonApp], str]
SubmitLine = Callable[[ToonApp, Pilot[None], str], Awaitable[None]]


async def test_app_mounts_all_host_regions(app: ToonApp) -> None:
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()

        assert app.query_one(AppHeader) is not None
        assert app.query_one(ContentArea) is not None
        assert app.query_one(Repl) is not None
        assert app.query_one(AppFooter) is not None


async def test_startup_summary_written_to_repl(app: ToonApp, read_repl: ReadRepl) -> None:
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()

        text = read_repl(app)
        assert "No plugins found" in text
        assert "help" in text


async def test_title_is_shown_in_the_header(app: ToonApp) -> None:
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()

        title = app.query_one(AppHeader).query_one("#header-title", Static)
        assert str(title.content) == app.title
        assert ToonApp.TITLE == "Toon"


async def test_help_lists_builtin_commands(
    app: ToonApp, read_repl: ReadRepl, submit: SubmitLine
) -> None:
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()

        await submit(app, pilot, "help")

        text = read_repl(app)
        for name in ("help", "clear", "reset", "plugins", "echo"):
            assert name in text


async def test_typing_a_line_in_the_input_runs_it(app: ToonApp, read_repl: ReadRepl) -> None:
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        assert pilot.app.focused is not None

        # Type via the real key path rather than assigning the widget value.
        await pilot.press("e", "c", "h", "o", "space", "h", "i", "enter")
        await pilot.pause()

        text = read_repl(app)
        assert "> echo hi" in text
        assert "hi" in text
