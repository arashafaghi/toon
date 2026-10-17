"""Discover and load local plugins.

A plugin is an immediate child directory of ``plugins/`` that contains a
``plugin.py`` module exposing a module-level ``register(registry)`` function.

Loading is deliberately forgiving: import and registration failures are
captured per plugin so one broken plugin can never stop the host or the other
plugins. Plugins are trusted, in-process Python -- there is no sandbox, hot
reload, or isolation.
"""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path

from toon.api import ExtensionRegistry

__all__ = ["LoadReport", "PluginResult", "discover_plugins", "load_plugins"]

_ENTRY_MODULE = "plugin.py"


@dataclass(frozen=True, slots=True)
class PluginResult:
    """Outcome of loading a single plugin.

    ``error`` is ``None`` on success, otherwise a short
    ``"<ExceptionType>: <message>"`` description.
    """

    name: str
    error: str | None = None


@dataclass(frozen=True, slots=True)
class LoadReport:
    """Result of loading every discovered plugin, in discovery order."""

    results: tuple[PluginResult, ...]

    @property
    def loaded_names(self) -> tuple[str, ...]:
        """Names of plugins that loaded successfully, in insertion order."""
        return tuple(result.name for result in self.results if result.error is None)

    @property
    def failures(self) -> tuple[PluginResult, ...]:
        """Results for plugins that failed, in insertion order."""
        return tuple(result for result in self.results if result.error is not None)

    def summaries(self) -> tuple[tuple[str, str | None], ...]:
        """``(name, error)`` for every result, order preserved."""
        return tuple((result.name, result.error) for result in self.results)


def discover_plugins(plugins_dir: Path) -> tuple[Path, ...]:
    """Return the ``plugin.py`` paths of immediate child directories.

    Directories without a ``plugin.py`` are ignored. Results are sorted by
    directory name for deterministic loading. A missing or non-directory
    ``plugins_dir`` yields an empty tuple instead of raising.
    """
    if not plugins_dir.is_dir():
        return ()
    candidates = (
        child / _ENTRY_MODULE
        for child in plugins_dir.iterdir()
        if child.is_dir() and (child / _ENTRY_MODULE).is_file()
    )
    return tuple(sorted(candidates, key=lambda path: path.parent.name))


def load_plugins(plugins_dir: Path, registry: ExtensionRegistry) -> LoadReport:
    """Discover, import, and register each plugin, returning a report.

    Each plugin's name is its directory name. Import and registration errors
    are isolated: they are recorded as a failure and loading continues with the
    next plugin. This function never raises for a misbehaving plugin.
    """
    results: list[PluginResult] = []
    for plugin_path in discover_plugins(plugins_dir):
        name = plugin_path.parent.name
        try:
            module = _import_plugin(name, plugin_path)
            register = getattr(module, "register", None)
            if not callable(register):
                results.append(PluginResult(name, "plugin.py has no register(registry) function"))
                continue
            register(registry)
        except Exception as exc:  # noqa: BLE001 - isolation is the point
            results.append(PluginResult(name, f"{type(exc).__name__}: {exc}"))
            continue
        results.append(PluginResult(name))
    return LoadReport(tuple(results))


def _import_plugin(name: str, plugin_path: Path) -> object:
    """Import ``plugin_path`` as a uniquely named, flat module.

    The module is registered under a sanitized, plugin-specific name in
    :data:`sys.modules` so that sibling plugins never collide on the generic
    ``plugin`` name.
    """
    module_name = f"toon_plugins_{_sanitize(name)}"
    spec = importlib.util.spec_from_file_location(module_name, plugin_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load plugin module from {plugin_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _sanitize(name: str) -> str:
    """Return ``name`` with every non-identifier character replaced by ``_``."""
    sanitized = "".join(char if char.isidentifier() or char.isdigit() else "_" for char in name)
    return sanitized or "_"
