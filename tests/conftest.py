"""Shared test helpers.

The only test double defined here is an in-memory :class:`ViewHost`: it is a
true boundary (the host UI), so recording the calls made against it is the
observable behavior tests should assert on. No host code under test is mocked.
"""

from __future__ import annotations

import pytest


class RecordingViewHost:
    """A :class:`~toon.api.ViewHost` that records every call it receives."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None]] = []

    def open_view(self, name: str) -> None:
        self.calls.append(("open_view", name))

    def close_view(self, name: str) -> None:
        self.calls.append(("close_view", name))

    def open_screen(self, name: str) -> None:
        self.calls.append(("open_screen", name))

    def clear_output(self) -> None:
        self.calls.append(("clear_output", None))

    def reset_views(self) -> None:
        self.calls.append(("reset_views", None))

    def arguments_to(self, method: str) -> list[str | None]:
        """Return the arguments of every call to ``method``, in call order."""
        return [argument for name, argument in self.calls if name == method]


@pytest.fixture
def view_host() -> RecordingViewHost:
    """A fresh recording host for each test."""
    return RecordingViewHost()
