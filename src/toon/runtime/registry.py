"""In-memory registry of commands and UI contributions.

The registry is the host's single source of truth for what the built-ins and
any plugins have registered. Names are validated with pydantic, duplicates are
rejected with a user-facing :class:`~toon.api.RegistrationError`, and insertion
order is preserved so ``help`` output stays stable.

Textual types are referenced only under ``TYPE_CHECKING``: the runtime layer
stores factories but never imports rendering code at runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, ValidationError

from toon.api import (
    Command,
    ExtensionRegistry,
    RegistrationError,
    ScreenFactory,
    WidgetFactory,
)

if TYPE_CHECKING:
    from textual.screen import Screen
    from textual.widget import Widget

__all__ = ["BarItem", "CommandInfo", "Registry", "ViewInfo"]

_NAME_PATTERN = r"^[A-Za-z][A-Za-z0-9_-]*$"


class _Name(BaseModel):
    """Throwaway model used only to validate a registration name."""

    name: str = Field(min_length=1, pattern=_NAME_PATTERN)


@dataclass(frozen=True, slots=True)
class CommandInfo:
    """A command's name and description, for listings."""

    name: str
    description: str


@dataclass(frozen=True, slots=True)
class ViewInfo:
    """A screen or widget's name, description, and tab title."""

    name: str
    description: str
    title: str = ""


@dataclass(frozen=True, slots=True)
class BarItem:
    """A widget contribution for the header/footer bar.

    ``view`` is the view it belongs to; the host shows the item only while that
    view is open. ``view is None`` means the item is always shown.
    """

    name: str
    factory: WidgetFactory
    view: str | None = None


def _checked_name(kind: str, name: str) -> None:
    """Raise :class:`RegistrationError` when ``name`` is not a valid identifier."""
    try:
        _Name(name=name)
    except ValidationError:
        raise RegistrationError(
            f"{kind} name {name!r} is invalid: expected a name starting with a "
            "letter and containing only letters, digits, underscores, or hyphens."
        ) from None


class Registry(ExtensionRegistry):
    """Insertion-ordered store of commands, screen factories, and widget factories.

    Commands, screens, and widgets live in independent namespaces, so a command
    and a screen may legitimately share the same name.
    """

    def __init__(self) -> None:
        self._commands: dict[str, Command] = {}
        self._screens: dict[str, tuple[ScreenFactory, str]] = {}
        self._widgets: dict[str, tuple[WidgetFactory, str, str]] = {}
        # Bar items: name -> (factory, description, order, view).
        self._header_items: dict[str, tuple[WidgetFactory, str, int, str | None]] = {}
        self._footer_items: dict[str, tuple[WidgetFactory, str, int, str | None]] = {}

    # --- ExtensionRegistry implementation ----------------------------------

    def register_command(self, command: Command) -> None:
        """Register ``command``; raise on an invalid or duplicate name."""
        _checked_name("Command", command.name)
        if command.name in self._commands:
            raise RegistrationError(f"Command '{command.name}' is already registered.")
        self._commands[command.name] = command

    def register_screen(self, name: str, factory: ScreenFactory, *, description: str = "") -> None:
        """Register a screen factory under ``name``; raise on a duplicate."""
        _checked_name("Screen", name)
        if name in self._screens:
            raise RegistrationError(f"Screen '{name}' is already registered.")
        self._screens[name] = (factory, description)

    def register_widget(
        self,
        name: str,
        factory: WidgetFactory,
        *,
        description: str = "",
        title: str | None = None,
    ) -> None:
        """Register a widget factory under ``name``; raise on a duplicate.

        ``title`` is the label shown for the view's tab; it defaults to ``name``.
        """
        _checked_name("Widget", name)
        if name in self._widgets:
            raise RegistrationError(f"Widget '{name}' is already registered.")
        self._widgets[name] = (factory, description, title or name)

    def register_header_item(
        self,
        name: str,
        factory: WidgetFactory,
        *,
        description: str = "",
        order: int = 0,
        view: str | None = None,
    ) -> None:
        """Register a widget shown in the header bar; raise on a duplicate.

        Lower ``order`` values appear first (registration order breaks ties).
        If ``view`` is set, the item is shown only while that view is open;
        otherwise it is shown for the whole session.
        """
        _checked_name("Header item", name)
        if name in self._header_items:
            raise RegistrationError(f"Header item '{name}' is already registered.")
        self._header_items[name] = (factory, description, order, view)

    def register_footer_item(
        self,
        name: str,
        factory: WidgetFactory,
        *,
        description: str = "",
        order: int = 0,
        view: str | None = None,
    ) -> None:
        """Register a widget shown in the footer bar; raise on a duplicate.

        Lower ``order`` values appear first (registration order breaks ties).
        If ``view`` is set, the item is shown only while that view is open;
        otherwise it is shown for the whole session.
        """
        _checked_name("Footer item", name)
        if name in self._footer_items:
            raise RegistrationError(f"Footer item '{name}' is already registered.")
        self._footer_items[name] = (factory, description, order, view)

    # --- Queries -----------------------------------------------------------

    @property
    def commands(self) -> tuple[Command, ...]:
        """Registered commands, in insertion order."""
        return tuple(self._commands.values())

    def command_infos(self) -> tuple[CommandInfo, ...]:
        """Name/description pairs for every registered command."""
        return tuple(
            CommandInfo(name=command.name, description=command.description)
            for command in self._commands.values()
        )

    def get_command(self, name: str) -> Command | None:
        """Return the command registered under ``name``, or ``None``."""
        return self._commands.get(name)

    def screen_infos(self) -> tuple[ViewInfo, ...]:
        """Name/description pairs for every registered screen."""
        return tuple(
            ViewInfo(name=name, description=description, title=name)
            for name, (_, description) in self._screens.items()
        )

    def widget_infos(self) -> tuple[ViewInfo, ...]:
        """Name/description/title for every registered widget."""
        return tuple(
            ViewInfo(name=name, description=description, title=title)
            for name, (_, description, title) in self._widgets.items()
        )

    def header_items(self) -> tuple[BarItem, ...]:
        """Every header item, in display order."""
        return self._bar_items(self._header_items)

    def footer_items(self) -> tuple[BarItem, ...]:
        """Every footer item, in display order."""
        return self._bar_items(self._footer_items)

    @staticmethod
    def _bar_items(
        items: dict[str, tuple[WidgetFactory, str, int, str | None]],
    ) -> tuple[BarItem, ...]:
        ordered = sorted(items.items(), key=lambda item: item[1][2])
        return tuple(
            BarItem(name, factory, view) for name, (factory, _desc, _order, view) in ordered
        )

    def has_screen(self, name: str) -> bool:
        """Return ``True`` when a screen is registered under ``name``."""
        return name in self._screens

    def has_widget(self, name: str) -> bool:
        """Return ``True`` when a widget is registered under ``name``."""
        return name in self._widgets

    # --- Factory invocation ------------------------------------------------

    def create_screen(self, name: str) -> Screen:
        """Return a fresh screen from the factory registered under ``name``."""
        try:
            factory, _ = self._screens[name]
        except KeyError:
            raise KeyError(f"No screen registered under '{name}'.") from None
        return factory()

    def create_view(self, name: str) -> tuple[Widget, str]:
        """Return a fresh widget and its tab title for the view ``name``."""
        try:
            factory, _, title = self._widgets[name]
        except KeyError:
            raise KeyError(f"No widget registered under '{name}'.") from None
        return factory(), title

    def create_widget(self, name: str) -> Widget:
        """Return a fresh widget from the factory registered under ``name``."""
        return self.create_view(name)[0]
