"""Command palette configuration for Toon.

This is the single home for everything the Textual command palette (``Ctrl+P``)
shows:

* :class:`RegistryCommands` exposes every command registered on the host's
  ``Registry`` -- built-in and plugin commands alike -- and runs the selected
  command through the REPL, so the palette and the REPL behave identically.
* :data:`SYSTEM_COMMANDS_TO_HIDE` is the one list to edit to drop unwanted
  Textual system commands (``Maximize``/``Minimize`` by default).
* :class:`PaletteSystemCommands` applies that filter to the host app, and
  :func:`build_commands` returns the provider set used for ``App.COMMANDS``.

To change what appears in the palette, edit this file only.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from functools import partial
from typing import TYPE_CHECKING, Any, Protocol, cast

from textual.app import SystemCommand
from textual.command import DiscoveryHit, Hit, Hits, Provider
from textual.screen import Screen
from textual.system_commands import SystemCommandsProvider

if TYPE_CHECKING:
    from toon.runtime.registry import CommandInfo, Registry

__all__ = [
    "SYSTEM_COMMANDS_TO_HIDE",
    "PaletteSystemCommands",
    "RegistryCommands",
    "build_commands",
]

#: Titles of Textual's built-in system commands to omit from the palette.
#: Set to an empty set to keep them all.
SYSTEM_COMMANDS_TO_HIDE: frozenset[str] = frozenset({"Maximize", "Minimize"})

#: Element type of Textual's ``App.COMMANDS``: a provider class, or a
#: zero-argument factory returning one.
CommandProvider = type[Provider] | Callable[[], type[Provider]]


class _PaletteHost(Protocol):
    """The slice of the host application the palette provider needs."""

    registry: Registry

    async def run_command(self, name: str) -> None:
        """Run the registered command ``name`` and show its output in the REPL."""
        ...


class RegistryCommands(Provider):
    """Palette provider that lists every command registered on the host."""

    async def search(self, query: str) -> Hits:
        """Yield fuzzy matches for ``query`` across all registered commands."""
        matcher = self.matcher(query)
        for info in self._command_infos():
            if (score := matcher.match(info.name)) > 0:
                yield Hit(
                    score,
                    matcher.highlight(info.name),
                    partial(self._host().run_command, info.name),
                    text=info.name,
                    help=info.description or None,
                )

    async def discover(self) -> Hits:
        """Show every registered command before the user types anything."""
        for info in self._command_infos():
            yield DiscoveryHit(
                info.name,
                partial(self._host().run_command, info.name),
                text=info.name,
                help=info.description or None,
            )

    def _host(self) -> _PaletteHost:
        return cast("_PaletteHost", self.app)

    def _command_infos(self) -> tuple[CommandInfo, ...]:
        return self._host().registry.command_infos()


class PaletteSystemCommands:
    """Mixin for the host ``App`` that filters Textual's system commands.

    Apply as the left-most base so ``super()`` reaches ``App``::

        class ToonApp(PaletteSystemCommands, App[None]):
            ...
    """

    def get_system_commands(self, screen: Screen[Any]) -> Iterable[SystemCommand]:
        """Yield Textual's system commands minus anything in :data:`SYSTEM_COMMANDS_TO_HIDE`."""
        for command in super().get_system_commands(screen):  # type: ignore[misc]
            if command.title not in SYSTEM_COMMANDS_TO_HIDE:
                yield command


def build_commands() -> set[type[Provider]]:
    """Return the provider set to assign to ``App.COMMANDS``.

    Keeps Textual's system commands (Theme, Quit, Keys, Screenshot, ...) and
    adds :class:`RegistryCommands` for the host's registered commands.
    """
    return {SystemCommandsProvider, RegistryCommands}
