"""Built-in REPL commands registered by the host at startup.

Handlers depend only on the public extension API and the registry's query
methods; they never reach into the host or the REPL widget.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from toon.api import Command, CommandContext
from toon.runtime.registry import CommandInfo, Registry, ViewInfo

__all__ = ["PluginSummary", "register_builtins"]

#: ``(plugin name, error message or None)`` for one plugin load attempt.
PluginSummary = tuple[str, str | None]


def register_builtins(
    registry: Registry,
    *,
    plugins: Callable[[], Sequence[PluginSummary]] = tuple,
) -> None:
    """Register the host built-ins on ``registry``.

    ``plugins`` is a zero-argument callable returning the current plugin load
    summaries; it defaults to an empty sequence so the host can call this before
    plugin discovery exists.
    """
    registry.register_command(
        Command("help", _make_help(registry), "List available commands, screens, and widgets.")
    )
    registry.register_command(Command("clear", _clear, "Clear the REPL output."))
    registry.register_command(
        Command("plugins", _make_plugins(plugins), "List loaded plugins and load failures.")
    )
    registry.register_command(Command("echo", _echo, "Print the given text back."))


def _label(name: str, description: str) -> str:
    """Format ``name — description`` (or just ``name`` when undescribed)."""
    return f"{name} — {description}" if description else name


def _make_help(registry: Registry) -> Callable[[CommandContext], str]:
    """Build the ``help`` handler backed by ``registry``'s current contents."""

    def help_command(ctx: CommandContext) -> str:
        if ctx.args:
            name = ctx.args[0]
            command = registry.get_command(name)
            if command is None:
                return f"Unknown command '{name}'."
            return _label(command.name, command.description)

        lines = ["Commands:"]
        lines.extend(_format_command(info) for info in registry.command_infos())

        screens = registry.screen_infos()
        if screens:
            lines.append("")
            lines.append("Screens:")
            lines.extend(_format_view(info) for info in screens)

        widgets = registry.widget_infos()
        if widgets:
            lines.append("")
            lines.append("Widgets:")
            lines.extend(_format_view(info) for info in widgets)

        return "\n".join(lines)

    return help_command


def _format_command(info: CommandInfo) -> str:
    return f"  {_label(info.name, info.description)}"


def _format_view(info: ViewInfo) -> str:
    return f"  {_label(info.name, info.description)}"


def _clear(ctx: CommandContext) -> None:
    """Clear the REPL output pane."""
    ctx.host.clear_output()
    return None


def _echo(ctx: CommandContext) -> str:
    """Return the supplied arguments joined by single spaces."""
    return " ".join(ctx.args)


def _make_plugins(
    plugins: Callable[[], Sequence[PluginSummary]],
) -> Callable[[CommandContext], str]:
    """Build the ``plugins`` handler reporting load successes and failures."""

    def plugins_command(ctx: CommandContext) -> str:
        summaries = plugins()
        if not summaries:
            return "No plugins loaded."
        lines = [
            f"{name}: ok" if error is None else f"{name}: FAILED - {error}"
            for name, error in summaries
        ]
        return "\n".join(lines)

    return plugins_command
