"""Example plugin: a trivial text-only command.

Demonstrates the minimal plugin shape -- import only from :mod:`toon.api` and
expose a module-level ``register(registry)`` entry point.
"""

from __future__ import annotations

from toon.api import Command, CommandContext, ExtensionRegistry


def hello(ctx: CommandContext) -> str:
    """Return a greeting, addressing any arguments or ``world`` by default."""
    who = " ".join(ctx.args) if ctx.args else "world"
    return f"Hello, {who}!"


def register(registry: ExtensionRegistry) -> None:
    """Register the ``hello`` command."""
    registry.register_command(Command("hello", hello, description="Say hello."))
