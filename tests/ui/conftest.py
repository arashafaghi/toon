"""Shared fixtures for host UI behavior tests.

Every test drives a real :class:`toon.app.ToonApp` through Textual's headless
``App.run_test`` pilot. The app is built with an **empty, isolated** plugins
directory (``tmp_path``) so the bundled demo plugins never influence results.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path

import pytest
from textual.pilot import Pilot
from textual.widgets import Input, RichLog

from toon.app import ToonApp
from toon.ui.repl import Repl


@pytest.fixture
def app(tmp_path: Path) -> ToonApp:
    """Return a ``ToonApp`` isolated to a temp plugins dir and state file."""
    return ToonApp(plugins_dir=tmp_path, state_path=tmp_path / "state.json")


@pytest.fixture
def read_repl() -> Callable[[ToonApp], str]:
    """Return a function that reads the REPL output log as plain text."""

    def _read(application: ToonApp) -> str:
        log = application.query_one(Repl).query_one(RichLog)
        return "\n".join(line.text.rstrip() for line in log.lines)

    return _read


@pytest.fixture
def submit() -> Callable[[ToonApp, Pilot[None], str], Awaitable[None]]:
    """Return a coroutine that submits ``text`` through the REPL input widget.

    This drives the real ``Input`` -> ``Input.Submitted`` -> ``Repl`` path, not
    the widget's private internals.
    """

    async def _submit(application: ToonApp, pilot: Pilot[None], text: str) -> None:
        field = application.query_one(Repl).query_one(Input)
        field.focus()
        field.value = text
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

    return _submit
