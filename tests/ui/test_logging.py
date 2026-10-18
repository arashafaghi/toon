"""Behavior tests for routing Loguru records into the REPL output area."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from toon.api import logger
from toon.app import ToonApp

ReadRepl = Callable[[ToonApp], str]


async def test_records_emitted_through_the_api_appear_in_the_repl(
    app: ToonApp, read_repl: ReadRepl
) -> None:
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()

        logger.info("record-from-the-api")

        await pilot.pause()
        assert "record-from-the-api" in read_repl(app)


async def test_records_emitted_before_the_repl_mounts_are_flushed(
    app: ToonApp, read_repl: ReadRepl
) -> None:
    # Emitted after the app object exists but before ``run_test`` mounts the
    # REPL, so the sink must buffer it and flush on attach.
    logger.info("buffered-before-mount")

    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()

        assert "buffered-before-mount" in read_repl(app)


async def test_plugin_load_failure_is_logged_and_reported(
    tmp_path: Path, read_repl: ReadRepl
) -> None:
    plugin_dir = tmp_path / "broken"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.py").write_text("raise RuntimeError('nope')\n")

    app = ToonApp(plugins_dir=tmp_path, state_path=tmp_path / "state.json")

    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()

        text = read_repl(app)
        # Buffered Loguru record from the plugin loader during __init__ ...
        assert "broken" in text
        assert "nope" in text
