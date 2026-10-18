"""Behavior tests for the host header bar."""

from __future__ import annotations

import re

from textual.widgets import Static

from toon.app import ToonApp
from toon.ui.header import AppHeader

_CLOCK_RE = re.compile(r"^\d{2}:\d{2}:\d{2}$")


def _register_view(app: ToonApp, name: str) -> None:
    app.registry.register_widget(
        name, lambda: Static(f"{name} body", id=f"body-{name}"), title=name
    )


async def test_header_shows_the_title_and_a_clock(app: ToonApp) -> None:
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()

        header = app.query_one(AppHeader)
        assert str(header.query_one("#header-title", Static).content) == app.title

        clock = str(header.query_one("#header-clock", Static).content)
        assert _CLOCK_RE.match(clock), clock


async def test_session_header_item_is_shown(app: ToonApp) -> None:
    app.registry.register_header_item(
        "session-item",
        lambda: Static("session", id="header-session-item"),
    )

    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()

        header = app.query_one(AppHeader)
        assert len(header.query("#header-session-item")) == 1


async def test_view_header_item_appears_only_while_the_view_is_open(app: ToonApp) -> None:
    _register_view(app, "beta")
    app.registry.register_header_item(
        "view-item",
        lambda: Static("view", id="header-view-item"),
        view="beta",
    )

    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        header = app.query_one(AppHeader)

        # Nothing open yet: a view-scoped item must not be present.
        assert len(header.query("#header-view-item")) == 0

        app.open_view("beta")
        await pilot.pause()
        assert len(header.query("#header-view-item")) == 1

        app.reset_views()
        await pilot.pause()
        assert len(header.query("#header-view-item")) == 0
