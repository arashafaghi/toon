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
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

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
type ScreenFactory = Callable[[], Screen[Any]]
type WidgetFactory = Callable[[], Widget]


@runtime_checkable
class ViewHost(Protocol):
    """Host-facing navigation, injected into handlers via ``CommandContext``.

    Kept intentionally tiny and free of Textual types so plugins never reach
    into the application object directly.
    """

    def open_view(self, name: str) -> None:
        """Open the registered widget ``name`` in the host content area.

        Each open view is shown in its own tab. If a view with that name is
        already open it is **activated** rather than opened twice; otherwise a
        fresh instance is mounted in a new tab.
        """

    def close_view(self, name: str) -> None:
        """Close the open view ``name``, if any, destroying its widget."""

    def open_screen(self, name: str) -> None:
        """Push the registered screen ``name`` onto the screen stack."""

    def clear_output(self) -> None:
        """Clear the REPL output pane (used by the built-in ``clear`` command)."""

    def reset_views(self) -> None:
        """Close every open view and screen (used by the built-in ``reset`` command).

        Returns to the base screen and unmounts all widget contributions from
        the host content area, leaving the host in a clean starting state.
        """


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

    def register_widget(
        self,
        name: str,
        factory: WidgetFactory,
        *,
        description: str = "",
        title: str | None = None,
    ) -> None:
        """Register a widget factory; raise ``RegistrationError`` on a duplicate name.

        ``title`` is the label shown for the view's tab when it is opened; it
        defaults to ``name``.
        """

    def register_header_item(
        self,
        name: str,
        factory: WidgetFactory,
        *,
        description: str = "",
        order: int = 0,
        view: str | None = None,
    ) -> None:
        """Register a widget for the host header bar; raise on a duplicate name.

        Lower ``order`` values appear first (registration order breaks ties).
        If ``view`` is set, the item shows only while that view is open;
        otherwise it shows for the whole session.
        """

    def register_footer_item(
        self,
        name: str,
        factory: WidgetFactory,
        *,
        description: str = "",
        order: int = 0,
        view: str | None = None,
    ) -> None:
        """Register a widget for the host footer bar; raise on a duplicate name.

        Lower ``order`` values appear first (registration order breaks ties).
        If ``view`` is set, the item shows only while that view is open;
        otherwise it shows for the whole session.
        """
