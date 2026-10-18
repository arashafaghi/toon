"""Behavior tests for the persistent session state."""

from __future__ import annotations

import json
from pathlib import Path

from toon.runtime.state import AppState, StateStore, default_state_path


def test_missing_file_is_created_empty(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "state.json"
    state = StateStore(path).load()

    assert state == AppState()
    assert path.exists()
    payload = json.loads(path.read_text())
    assert payload["open_views"] == []
    assert payload["history"] == []


def test_round_trip(tmp_path: Path) -> None:
    store = StateStore(tmp_path / "state.json")
    store.save(AppState(open_views=("alpha", "beta"), history=("echo hi", "help")))

    loaded = store.load()
    assert loaded.open_views == ("alpha", "beta")
    assert loaded.history == ("echo hi", "help")


def test_corrupt_file_degrades_to_empty(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text("{ this is not json")

    assert StateStore(path).load() == AppState()


def test_non_string_entries_are_dropped(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text(json.dumps({"version": 1, "open_views": [1, "ok", None], "history": ["a", 2]}))

    loaded = StateStore(path).load()
    assert loaded.open_views == ("ok",)
    assert loaded.history == ("a",)


def test_unexpected_shape_is_treated_as_empty(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text(json.dumps(["not", "a", "dict"]))

    assert StateStore(path).load() == AppState()


def test_default_path_honours_env_override(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TOON_STATE_FILE", str(tmp_path / "custom.json"))

    assert default_state_path() == tmp_path / "custom.json"


def test_default_path_uses_xdg_config(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("TOON_STATE_FILE", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    assert default_state_path() == tmp_path / "toon" / "state.json"
