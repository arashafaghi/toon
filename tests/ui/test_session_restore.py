"""The app remembers the open views and restores them on startup."""

from __future__ import annotations

import json
from pathlib import Path

from textual.widgets import Static, TabPane

from toon.app import ToonApp
from toon.ui.content import ContentArea


def _state_file(tmp_path: Path) -> Path:
    return tmp_path / "state.json"


def _open_views(path: Path) -> list[str]:
    return json.loads(path.read_text())["open_views"]


def test_missing_state_file_is_created(tmp_path: Path) -> None:
    state = tmp_path / "nested" / "state.json"

    ToonApp(plugins_dir=tmp_path, state_path=state)

    assert state.exists()
    assert _open_views(state) == []


async def test_restores_views_from_saved_state(tmp_path: Path) -> None:
    state = _state_file(tmp_path)
    state.write_text(json.dumps({"version": 1, "open_views": ["alpha"]}))

    app = ToonApp(plugins_dir=tmp_path, state_path=state)
    app.registry.register_widget("alpha", lambda: Static("A"), title="Alpha")

    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        assert len(app.query(TabPane)) == 1
        assert app.query_one(ContentArea).has("alpha")


async def test_persists_open_close_and_reset(tmp_path: Path) -> None:
    state = _state_file(tmp_path)
    app = ToonApp(plugins_dir=tmp_path, state_path=state)
    app.registry.register_widget("alpha", lambda: Static("A"), title="Alpha")

    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()

        app.open_view("alpha")
        await pilot.pause()
        assert _open_views(state) == ["alpha"]

        app.close_view("alpha")
        await pilot.pause()
        assert _open_views(state) == []

        app.open_view("alpha")
        await pilot.pause()
        app.reset_views()
        await pilot.pause()
        assert _open_views(state) == []


async def test_unknown_saved_views_are_skipped(tmp_path: Path) -> None:
    state = _state_file(tmp_path)
    state.write_text(json.dumps({"version": 1, "open_views": ["ghost", "alpha"]}))

    app = ToonApp(plugins_dir=tmp_path, state_path=state)
    app.registry.register_widget("alpha", lambda: Static("A"), title="Alpha")

    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        content = app.query_one(ContentArea)
        assert content.has("alpha")
        assert not content.has("ghost")
        assert len(app.query(TabPane)) == 1
