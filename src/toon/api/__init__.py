"""Public extension API for Toon plugins.

Plugins should import from here (or :mod:`toon.api.extension`) and nothing else
from the host::

    from toon.api import Command, CommandContext, ExtensionRegistry


    def register(registry: ExtensionRegistry) -> None:
        registry.register_command(Command("greet", greet, "Say hello."))

Plugins can also log with ``from toon.api import logger``; records are shown in
the host's REPL output area.
"""

import importlib
from typing import TYPE_CHECKING

from loguru import logger

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

if TYPE_CHECKING:
    # Re-exported lazily (see __getattr__) so importing ``toon.api`` never pulls
    # in Textual or httpx; these imports exist only for type checkers.
    from toon.api.http import (
        Auth,
        BasicAuth,
        BearerAuth,
        HeaderAuth,
        HttpClient,
        HttpError,
        HttpResponse,
        NetrcAuth,
        NoAuth,
    )
    from toon.api.widgets import FlowLane, FlowMode, FlowTrack, render_track

__all__ = [
    "Auth",
    "BasicAuth",
    "BearerAuth",
    "Command",
    "CommandContext",
    "CommandHandler",
    "CommandResult",
    "ExtensionRegistry",
    "FlowLane",
    "FlowMode",
    "FlowTrack",
    "HeaderAuth",
    "HttpClient",
    "HttpError",
    "HttpResponse",
    "NetrcAuth",
    "NoAuth",
    "RegistrationError",
    "ScreenFactory",
    "ViewHost",
    "WidgetFactory",
    "logger",
    "render_track",
]

#: Names re-exported lazily, mapped to the module that defines them.
_LAZY_EXPORTS: dict[str, frozenset[str]] = {
    "toon.api.http": frozenset(
        {
            "Auth",
            "BasicAuth",
            "BearerAuth",
            "HeaderAuth",
            "HttpClient",
            "HttpError",
            "HttpResponse",
            "NetrcAuth",
            "NoAuth",
        }
    ),
    "toon.api.widgets": frozenset({"FlowLane", "FlowMode", "FlowTrack", "render_track"}),
}


def __getattr__(name: str) -> object:
    """Lazily expose the UI and HTTP helpers of the public API.

    Keeping these lazy means ``import toon.api`` (used by the core runtime) does
    not pull in Textual or httpx; only plugins that actually ask for them do.
    """
    for module_name, names in _LAZY_EXPORTS.items():
        if name in names:
            return getattr(importlib.import_module(module_name), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
