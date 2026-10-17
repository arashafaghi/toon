"""Public extension API for the Toon plugin runner.

This module is the *only* surface a plugin is allowed to import from the host.
It deliberately depends on nothing from the host internals and references
Textual types only under ``TYPE_CHECKING`` (as forward references), so the core
registry/dispatcher stay free of rendering concerns at runtime.

The contracts in this module are frozen for the milestone. Changing any public
signature requires an architecture update in ``docs/architecture.md`` first.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from textual.screen import Screen
    from textual.widget import Widget

__all__ = [
    "Command",
    "CommandContext",
    "CommandHandler",
    "CommandResult",
    "ExtensionRegistry",
    "RegistrationError",
    "ScreenFactory",
    "ViewHost",
    "WidgetFactory",
]


class RegistrationError(Exception):
    """Raised when a command, screen, or widget cannot be registered.

    The usual cause is a duplicate or invalid name. Messages are written to be
    shown directly to a user.
    """


# A factory must return a *fresh* Textual object on every call; the host never
# reuses an already-mounted widget or screen.
type ScreenFactory = Callable[[], Screen]
type WidgetFactory = Callable[[], Widget]


@runtime_checkable
class ViewHost(Protocol):
    """Host-facing navigation, injected into handlers via ``CommandContext``.

    Kept intentionally tiny and free of Textual types so plugins never reach
    into the application object directly.
    """

    def open_screen(self, name: str) -> None:
        """Push the registered screen ``name`` onto the screen stack."""

    def show_widget(self, name: str) -> None:
        """Mount the registered widget ``name`` in the host content area."""

    def clear_output(self) -> None:
        """Clear the REPL output pane (used by the built-in ``clear`` command)."""


@dataclass(frozen=True, slots=True)
class CommandContext:
    """Everything a handler needs: parsed arguments and host navigation."""

    args: tuple[str, ...]
    host: ViewHost


# Handlers may be synchronous or asynchronous and return text (``None`` means
# "no output"). The dispatcher normalises both conventions.
type CommandHandler = Callable[[CommandContext], str | None | Awaitable[str | None]]


@dataclass(frozen=True, slots=True)
class Command:
    """A single REPL command contributed by the host or a plugin."""

    name: str
    handler: CommandHandler
    description: str = ""


@dataclass(frozen=True, slots=True)
class CommandResult:
    """Outcome of dispatching one command line.

    ``error`` is ``None`` on success; otherwise it holds a readable message.
    The REPL renders both cases without raising.
    """

    command: str
    output: str = ""
    error: str | None = None

    @property
    def ok(self) -> bool:
        """Return ``True`` when the command completed without error."""
        return self.error is None


@runtime_checkable
class ExtensionRegistry(Protocol):
    """Registration surface passed to each plugin's ``register`` function."""

    def register_command(self, command: Command) -> None:
        """Register ``command``; raise ``RegistrationError`` on a duplicate name."""

    def register_screen(self, name: str, factory: ScreenFactory, *, description: str = "") -> None:
        """Register a screen factory; raise ``RegistrationError`` on a duplicate name."""

    def register_widget(self, name: str, factory: WidgetFactory, *, description: str = "") -> None:
        """Register a widget factory; raise ``RegistrationError`` on a duplicate name."""
