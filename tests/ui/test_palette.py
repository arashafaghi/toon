"""Behavior tests for the command palette integration."""

from __future__ import annotations

from collections.abc import Callable

from toon.api import Command, CommandContext
from toon.app import ToonApp
from toon.ui.palette import SYSTEM_COMMANDS_TO_HIDE, RegistryCommands

ReadRepl = Callable[[ToonApp], str]


async def test_system_commands_are_filtered(app: ToonApp) -> None:
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()

        titles = {command.title for command in app.get_system_commands(app.screen)}

        assert SYSTEM_COMMANDS_TO_HIDE == frozenset({"Maximize", "Minimize"})
        assert "Maximize" not in titles
        assert "Minimize" not in titles
        # Useful system commands are kept.
        assert "Quit" in titles
        assert "Theme" in titles


async def test_registry_provider_discovers_commands(app: ToonApp) -> None:
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()

        provider = RegistryCommands(app.screen)
        discovered = {hit.text for hit in [hit async for hit in provider.discover()]}

        for name in ("help", "clear", "reset", "plugins", "echo"):
            assert name in discovered


async def test_registry_provider_search_finds_a_command(app: ToonApp) -> None:
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()

        provider = RegistryCommands(app.screen)
        hits = [hit async for hit in provider.search("echo")]

        assert any(hit.text == "echo" for hit in hits)


async def test_running_a_command_through_the_palette_path(
    app: ToonApp, read_repl: ReadRepl
) -> None:
    def mark(ctx: CommandContext) -> str:
        return "the mark command ran"

    app.registry.register_command(Command("mark", mark, "Leave a marker."))

    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()

        await app.run_command("mark")
        await pilot.pause()

        text = read_repl(app)
        assert "> mark" in text
        assert "the mark command ran" in text


async def test_palette_uses_the_same_dispatcher_as_the_repl(
    app: ToonApp, read_repl: ReadRepl
) -> None:
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()

        await app.run_command("echo from-the-palette")
        await pilot.pause()

        assert "from-the-palette" in read_repl(app)
