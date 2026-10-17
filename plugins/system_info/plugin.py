"""Example plugin: report interpreter and platform details.

Text-only, and a slightly more realistic handler than ``hello``: it formats a
few facts about the running Python without touching any host internals.
"""

from __future__ import annotations

import platform
import sys

from toon.api import Command, CommandContext, ExtensionRegistry


def sysinfo(ctx: CommandContext) -> str:
    """Return a short interpreter/platform summary (arguments are ignored)."""
    version = platform.python_version()
    major, minor = sys.version_info[:2]
    return "\n".join(
        (
            f"Python: {major}.{minor} ({version})",
            f"Platform: {platform.platform()}",
            f"Executable: {sys.executable}",
        )
    )


def register(registry: ExtensionRegistry) -> None:
    """Register the ``sysinfo`` command."""
    registry.register_command(
        Command("sysinfo", sysinfo, description="Show Python and platform information.")
    )
