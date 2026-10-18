"""Behavior of plugin discovery and loading, including failure isolation."""

from __future__ import annotations

import textwrap
from pathlib import Path

from toon.api import Command
from toon.runtime.plugin_loader import (
    LoadReport,
    PluginResult,
    discover_plugins,
    load_plugins,
)
from toon.runtime.registry import Registry


def _write_plugin(plugins_dir: Path, name: str, body: str) -> Path:
    """Create ``plugins_dir/<name>/plugin.py`` with the dedented ``body``."""
    directory = plugins_dir / name
    directory.mkdir(parents=True)
    (directory / "plugin.py").write_text(textwrap.dedent(body), encoding="utf-8")
    return directory / "plugin.py"


def _good_plugin(command: str) -> str:
    return f"""
    from toon.api import Command

    def register(registry):
        registry.register_command(Command({command!r}, lambda ctx: "ok"))
    """


# --- discovery ---------------------------------------------------------------


def test_discover_plugins_is_sorted_and_ignores_non_plugins(tmp_path: Path) -> None:
    _write_plugin(tmp_path, "zeta", _good_plugin("zeta"))
    _write_plugin(tmp_path, "alpha", _good_plugin("alpha"))
    _write_plugin(tmp_path, "mid", _good_plugin("mid"))
    (tmp_path / "no_entry").mkdir()
    (tmp_path / "stray.py").write_text("", encoding="utf-8")

    discovered = discover_plugins(tmp_path)

    assert [path.parent.name for path in discovered] == ["alpha", "mid", "zeta"]
    assert all(path.name == "plugin.py" for path in discovered)


def test_discover_plugins_missing_or_non_directory_yields_nothing(tmp_path: Path) -> None:
    assert discover_plugins(tmp_path / "does-not-exist") == ()
    file_path = tmp_path / "a-file"
    file_path.write_text("", encoding="utf-8")
    assert discover_plugins(file_path) == ()


# --- loading -----------------------------------------------------------------


def test_load_plugins_registers_a_good_plugin(tmp_path: Path) -> None:
    _write_plugin(tmp_path, "hello", _good_plugin("hello"))
    registry = Registry()

    report = load_plugins(tmp_path, registry)

    assert registry.get_command("hello") is not None
    assert report.loaded_names == ("hello",)
    assert report.failures == ()
    assert report.summaries() == (("hello", None),)


def test_broken_plugin_is_isolated_and_others_still_load(tmp_path: Path) -> None:
    _write_plugin(tmp_path, "alpha", _good_plugin("alpha"))
    _write_plugin(tmp_path, "broken", "raise RuntimeError('kaboom')\n")
    _write_plugin(tmp_path, "zeta", _good_plugin("zeta"))
    registry = Registry()

    report = load_plugins(tmp_path, registry)

    assert registry.get_command("alpha") is not None
    assert registry.get_command("zeta") is not None
    assert report.loaded_names == ("alpha", "zeta")
    assert [failure.name for failure in report.failures] == ["broken"]
    assert "RuntimeError" in (report.failures[0].error or "")
    assert "kaboom" in (report.failures[0].error or "")
    assert [name for name, _ in report.summaries()] == ["alpha", "broken", "zeta"]


def test_plugin_without_register_is_reported_as_failure(tmp_path: Path) -> None:
    _write_plugin(tmp_path, "empty", "VALUE = 1\n")
    registry = Registry()

    report = load_plugins(tmp_path, registry)

    assert report.loaded_names == ()
    (failure,) = report.failures
    assert failure.name == "empty"
    assert "register" in (failure.error or "")


def test_plugin_registering_a_duplicate_name_fails_without_stopping_others(
    tmp_path: Path,
) -> None:
    _write_plugin(tmp_path, "dup", _good_plugin("help"))
    _write_plugin(tmp_path, "later", _good_plugin("later"))
    registry = Registry()
    registry.register_command(Command("help", lambda ctx: "builtin"))

    report = load_plugins(tmp_path, registry)

    assert registry.get_command("later") is not None
    assert report.loaded_names == ("later",)
    (failure,) = report.failures
    assert failure.name == "dup"
    assert "already registered" in (failure.error or "")


def test_plugin_that_raises_during_registration_is_isolated(tmp_path: Path) -> None:
    _write_plugin(
        tmp_path,
        "raises",
        """
        from toon.api import Command

        def register(registry):
            registry.register_command(Command("first", lambda ctx: None))
            raise ValueError("half registered")
        """,
    )
    _write_plugin(tmp_path, "fine", _good_plugin("fine"))
    registry = Registry()

    report = load_plugins(tmp_path, registry)

    assert registry.get_command("fine") is not None
    assert report.loaded_names == ("fine",)
    assert [failure.name for failure in report.failures] == ["raises"]
    assert "ValueError" in (report.failures[0].error or "")


# --- report ------------------------------------------------------------------


def test_load_report_summarises_successes_and_failures() -> None:
    report = LoadReport(
        (
            PluginResult("good"),
            PluginResult("bad", "ImportError: nope"),
        )
    )

    assert report.loaded_names == ("good",)
    assert report.failures == (PluginResult("bad", "ImportError: nope"),)
    assert report.summaries() == (("good", None), ("bad", "ImportError: nope"))
