"""Typed slices of the host application used by widgets that reach up to it.

Textual types ``Widget.app`` as the generic ``App``, which exposes none of the
host's own attributes. Rather than reaching through an unchecked ``Any``, a
widget that needs host state ``cast`` the app to a small protocol describing
exactly the slice it uses.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from toon.runtime.registry import Registry

__all__ = ["BarHost"]


class BarHost(Protocol):
    """The slice of the host app the header and footer bars need."""

    registry: Registry
