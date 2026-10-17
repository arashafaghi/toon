"""Public extension API for Toon plugins.

Plugins should import from here (or :mod:`toon.api.extension`) and nothing else
from the host::

    from toon.api import Command, CommandContext, ExtensionRegistry


    def register(registry: ExtensionRegistry) -> None:
        registry.register_command(Command("greet", greet, "Say hello."))
"""

from toon.api.extension import (
    Command,
    CommandContext,
    CommandHandler,
    CommandResult,
    ExtensionRegistry,
    RegistrationError,
    ScreenFactory,
    ViewHost,
    WidgetFactory,
)

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
