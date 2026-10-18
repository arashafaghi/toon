"""Behavior tests for the host footer bar."""

from __future__ import annotations

from typing import Any

from textual.widgets import Static

from toon.app import ToonApp
from toon.ui.footer import AppFooter


def _footer_keys(app: ToonApp) -> list[Any]:
    """The ``FooterKey`` widgets rendered by Textual's ``Footer``."""
    return list(app.query_one(AppFooter).query("FooterKey"))


async def test_visible_bindings_are_shown_and_hidden_are_not(app: ToonApp) -> None:
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()

        actions = {key.action for key in _footer_keys(app)}

        assert "quit" in actions
        assert "close_view" in actions
        # ``escape`` -> pop_view is registered with show=False.
        assert "pop_view" not in actions


async def test_command_palette_hint_is_present(app: ToonApp) -> None:
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()

        assert any(key.has_class("-command-palette") for key in _footer_keys(app))


async def test_registered_footer_item_is_shown(app: ToonApp) -> None:
    app.registry.register_footer_item(
        "session-item",
        lambda: Static("footer", id="footer-session-item"),
    )

    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()

        footer = app.query_one(AppFooter)
        assert len(footer.query("#footer-session-item")) == 1
