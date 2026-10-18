"""Behavior of the host's built-in commands, driven through a real dispatcher."""

from __future__ import annotations

from typing import Any

from textual.screen import Screen
from textual.widget import Widget

from toon.api import Command, CommandResult
from toon.runtime.builtins import PluginSummary, register_builtins
from toon.runtime.dispatcher import Dispatcher
from toon.runtime.registry import Registry


def _setup(
    *,
    plugins: Any = None,
    contributions: bool = False,
) -> tuple[Dispatcher, Registry]:
    registry = Registry()
    if plugins is None:
        register_builtins(registry)
    else:
        register_builtins(registry, plugins=plugins)
    if contributions:
        registry.register_screen("main", Screen, description="Main screen.")
        registry.register_widget("panel", Widget, description="A panel.")
    return Dispatcher(registry), registry


async def _run(dispatcher: Dispatcher, line: str, host: Any) -> CommandResult:
    return await dispatcher.dispatch(line, host=host)


# --- help --------------------------------------------------------------------


async def test_help_lists_every_registered_command(view_host: Any) -> None:
    dispatcher, registry = _setup()

    result = await _run(dispatcher, "help", view_host)

    assert result.ok is True
    assert result.output.startswith("Commands:")
    for info in registry.command_infos():
        assert info.name in result.output


async def test_help_includes_screens_and_widgets_when_present(view_host: Any) -> None:
    dispatcher, _ = _setup(contributions=True)

    result = await _run(dispatcher, "help", view_host)

    assert "Screens:" in result.output
    assert "main" in result.output
    assert "Widgets:" in result.output
    assert "panel" in result.output


async def test_help_omits_empty_sections(view_host: Any) -> None:
    dispatcher, _ = _setup()

    result = await _run(dispatcher, "help", view_host)

    assert "Screens:" not in result.output
    assert "Widgets:" not in result.output


async def test_help_for_a_named_command_shows_its_description(view_host: Any) -> None:
    dispatcher, _ = _setup()

    result = await _run(dispatcher, "help echo", view_host)

    assert result.output == "echo — Print the given text back."


async def test_help_for_an_unknown_command_is_readable(view_host: Any) -> None:
    dispatcher, _ = _setup()

    result = await _run(dispatcher, "help nope", view_host)

    assert result.ok is True
    assert result.output == "Unknown command 'nope'."


# --- simple commands ---------------------------------------------------------


async def test_echo_joins_arguments(view_host: Any) -> None:
    dispatcher, _ = _setup()

    result = await _run(dispatcher, "echo a b", view_host)

    assert result == CommandResult(command="echo", output="a b")


async def test_clear_asks_the_host_to_clear_output(view_host: Any) -> None:
    dispatcher, _ = _setup()

    result = await _run(dispatcher, "clear", view_host)

    assert result.ok is True
    assert result.output == ""
    assert view_host.arguments_to("clear_output") == [None]


async def test_reset_asks_the_host_to_reset_views(view_host: Any) -> None:
    dispatcher, _ = _setup()

    result = await _run(dispatcher, "reset", view_host)

    assert result.ok is True
    assert "Reset" in result.output
    assert view_host.arguments_to("reset_views") == [None]


# --- plugins -----------------------------------------------------------------


async def test_plugins_reports_none_loaded_by_default(view_host: Any) -> None:
    dispatcher, _ = _setup()

    result = await _run(dispatcher, "plugins", view_host)

    assert result.output == "No plugins loaded."


async def test_plugins_reports_successes_and_failures(view_host: Any) -> None:
    summaries: list[PluginSummary] = [
        ("hello", None),
        ("broken", "ImportError: nope"),
    ]
    dispatcher, _ = _setup(plugins=lambda: summaries)

    result = await _run(dispatcher, "plugins", view_host)

    assert result.output == "hello: ok\nbroken: FAILED - ImportError: nope"


async def test_plugins_reflects_the_provider_at_call_time(view_host: Any) -> None:
    summaries: list[PluginSummary] = []
    dispatcher, _ = _setup(plugins=lambda: summaries)

    before = await _run(dispatcher, "plugins", view_host)
    summaries.append(("late", None))
    after = await _run(dispatcher, "plugins", view_host)

    assert before.output == "No plugins loaded."
    assert after.output == "late: ok"


async def test_builtins_coexist_with_a_plugin_command(view_host: Any) -> None:
    dispatcher, registry = _setup()
    registry.register_command(Command("greet", lambda ctx: "hi"))

    result = await _run(dispatcher, "help", view_host)

    assert "greet" in result.output
    assert (await _run(dispatcher, "greet", view_host)).output == "hi"
