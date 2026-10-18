"""Persistent session state ("memory") for the host.

Remembers which views were open so they can be reopened on the next start. The
state file is optional: if it does not exist it is created empty, and any
problem reading it degrades to an empty state rather than failing startup.

The location defaults to ``$XDG_CONFIG_HOME/toon/state.json`` (or
``~/.config/toon/state.json``); override it with the ``TOON_STATE_FILE``
environment variable or by passing a path to :class:`StateStore`.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, replace
from pathlib import Path

from toon.api import logger

__all__ = ["AppState", "StateStore", "default_state_path"]

_STATE_VERSION = 1
_STATE_ENV = "TOON_STATE_FILE"


def default_state_path() -> Path:
    """Return the state file to use by default."""
    override = os.environ.get(_STATE_ENV)
    if override:
        return Path(override)
    config_home = os.environ.get("XDG_CONFIG_HOME")
    base = Path(config_home) if config_home else Path.home() / ".config"
    return base / "toon" / "state.json"


@dataclass(frozen=True, slots=True)
class AppState:
    """The remembered session state.

    ``open_views`` are the registered widget names that were open, in the order
    they were opened (so the last one is active again on restore). ``history``
    is the most recent REPL commands (oldest first).
    """

    open_views: tuple[str, ...] = ()
    history: tuple[str, ...] = ()

    def with_open_views(self, names: tuple[str, ...]) -> AppState:
        """Return a copy with ``open_views`` replaced."""
        return replace(self, open_views=names)

    def with_history(self, entries: tuple[str, ...]) -> AppState:
        """Return a copy with ``history`` replaced."""
        return replace(self, history=entries)


class StateStore:
    """Loads and saves :class:`AppState` as JSON on disk."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else default_state_path()

    def load(self) -> AppState:
        """Read the state, creating an empty file when it does not exist."""
        if not self.path.exists():
            self.save(AppState())
            return AppState()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not read state file {} ({}); starting fresh", self.path, exc)
            return AppState()
        return self._parse(data)

    def save(self, state: AppState) -> None:
        """Write ``state`` to disk (best effort)."""
        payload = {
            "version": _STATE_VERSION,
            "open_views": list(state.open_views),
            "history": list(state.history),
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        except OSError as exc:
            logger.warning("Could not write state file {} ({})", self.path, exc)

    @staticmethod
    def _parse(data: object) -> AppState:
        if not isinstance(data, dict):
            return AppState()
        return AppState(
            open_views=_string_list(data.get("open_views")),
            history=_string_list(data.get("history")),
        )


def _string_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str))
