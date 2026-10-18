"""REPL command history: prefix search on Up/Down and persistence."""

from __future__ import annotations

import json
from pathlib import Path

from textual.pilot import Pilot
from textual.widgets import Input

from toon.app import ToonApp
from toon.ui.repl import Repl


def _field(app: ToonApp) -> Input:
    return app.query_one(Repl).query_one(Input)


def _history(state: Path) -> list[str]:
    return json.loads(state.read_text())["history"]


async def _submit(pilot: Pilot[None], app: ToonApp, text: str) -> None:
    field = _field(app)
    field.focus()
    field.value = text
    await pilot.pause()
    await pilot.press("enter")
    await pilot.pause()


async def _type(pilot: Pilot[None], app: ToonApp, text: str) -> None:
    field = _field(app)
    field.focus()
    field.value = text
    await pilot.pause()


async def _press(pilot: Pilot[None], key: str) -> None:
    await pilot.press(key)
    await pilot.pause()


async def test_up_down_use_prefix_match(tmp_path: Path) -> None:
    app = ToonApp(plugins_dir=tmp_path, state_path=tmp_path / "state.json")

    async with app.run_test(size=(100, 40)) as pilot:
        for text in ("echo alpha 1", "echo beta 2", "echo alpha 3"):
            await _submit(pilot, app, text)

        field = _field(app)
        await _type(pilot, app, "echo alpha")

        await _press(pilot, "up")
        assert field.value == "echo alpha 3"
        await _press(pilot, "up")
        assert field.value == "echo alpha 1"  # skipped the non-matching entry
        await _press(pilot, "down")
        assert field.value == "echo alpha 3"
        await _press(pilot, "down")
        assert field.value == "echo alpha"  # draft restored


async def test_empty_prefix_walks_the_whole_history(tmp_path: Path) -> None:
    app = ToonApp(plugins_dir=tmp_path, state_path=tmp_path / "state.json")

    async with app.run_test(size=(100, 40)) as pilot:
        await _submit(pilot, app, "echo one")
        await _submit(pilot, app, "echo two")

        field = _field(app)
        await _type(pilot, app, "")

        await _press(pilot, "up")
        assert field.value == "echo two"
        await _press(pilot, "up")
        assert field.value == "echo one"
        await _press(pilot, "down")
        assert field.value == "echo two"


async def test_history_is_persisted_and_restored(tmp_path: Path) -> None:
    state = tmp_path / "state.json"

    first = ToonApp(plugins_dir=tmp_path, state_path=state)
    async with first.run_test(size=(100, 40)) as pilot:
        await _submit(pilot, first, "echo persisted")

    assert _history(state) == ["echo persisted"]

    second = ToonApp(plugins_dir=tmp_path, state_path=state)
    async with second.run_test(size=(100, 40)) as pilot:
        field = _field(second)
        await _type(pilot, second, "")
        await _press(pilot, "up")
        assert field.value == "echo persisted"


async def test_duplicates_ignored_and_history_capped(tmp_path: Path) -> None:
    state = tmp_path / "state.json"
    app = ToonApp(plugins_dir=tmp_path, state_path=state)

    async with app.run_test(size=(100, 40)) as pilot:
        await _submit(pilot, app, "echo same")
        await _submit(pilot, app, "echo same")  # consecutive duplicate ignored
        for i in range(25):
            await _submit(pilot, app, f"echo {i}")

    history = _history(state)
    assert len(history) == 20
    assert history[-1] == "echo 24"
