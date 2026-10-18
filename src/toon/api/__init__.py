"""Public extension API for Toon plugins.

Plugins should import from here (or :mod:`toon.api.extension`) and nothing else
from the host::

    from toon.api import Command, CommandContext, ExtensionRegistry


    def register(registry: ExtensionRegistry) -> None:
        registry.register_command(Command("greet", greet, "Say hello."))

Plugins can also log with ``from toon.api import logger``; records are shown in
the host's REPL output area.
"""

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
    # in Textual; this import exists only for type checkers.
    from toon.api.widgets import (
        FlowLane,
        FlowMode,
        FlowTrack,
        Orientation,
        TrackStyle,
        render_track,
    )

__all__ = [
    "Command",
    "CommandContext",
    "CommandHandler",
    "CommandResult",
    "ExtensionRegistry",
    "FlowLane",
    "FlowMode",
    "FlowTrack",
    "Orientation",
    "RegistrationError",
    "ScreenFactory",
    "TrackStyle",
    "ViewHost",
    "WidgetFactory",
    "logger",
    "render_track",
]

_WIDGET_EXPORTS = frozenset(
    {"FlowLane", "FlowMode", "FlowTrack", "Orientation", "TrackStyle", "render_track"}
)


def __getattr__(name: str) -> object:
    """Lazily expose the Textual-facing widgets in :mod:`toon.api.widgets`.

    Keeping this lazy means ``import toon.api`` (used by the core runtime) does
    not import Textual; only plugins that ask for a widget pull it in.
    """
    if name in _WIDGET_EXPORTS:
        from toon.api import widgets

        return getattr(widgets, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
