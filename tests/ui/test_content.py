"""Behavior tests for the host content area (tabbed view container)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from textual.pilot import Pilot
from textual.widgets import Static, TabbedContent, TabPane

from toon.api import Command, CommandContext
from toon.app import ToonApp
from toon.ui.content import ContentArea

SubmitLine = Callable[[ToonApp, Pilot[None], str], Awaitable[None]]


def _view(name: str) -> Static:
    """A uniquely identifiable widget body for the view ``name``.

    The id is distinct from the pane id (``view-<name>``) so a query for the
    body cannot accidentally match the tab pane.
    """
    return Static(f"{name} body", id=f"body-{name}")


def _register_view(app: ToonApp, name: str, *, title: str | None = None) -> None:
    app.registry.register_widget(name, lambda: _view(name), description="", title=title)


async def test_content_starts_with_empty_state_and_no_tabs(app: ToonApp) -> None:
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()

        content = app.query_one(ContentArea)
        assert content.open_names == frozenset()
        assert content.query_one("#view-empty", Static).display is True
        assert content.query_one(TabbedContent).display is False
        assert len(app.query(TabPane)) == 0


async def test_opening_a_view_creates_a_tab(app: ToonApp) -> None:
    _register_view(app, "alpha", title="Alpha Tab")

    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()

        app.open_view("alpha")
        await pilot.pause()

        content = app.query_one(ContentArea)
        assert content.open_names == frozenset({"alpha"})
        assert content.active_name == "alpha"
        assert content.query_one("#view-empty", Static).display is False
        assert content.query_one(TabbedContent).display is True
        assert app.query_one("#view-alpha", TabPane) is not None

        tab = content.query_one(TabbedContent).get_tab("view-alpha")
        assert tab.label_text == "Alpha Tab"


async def test_opening_the_same_view_activates_it_without_duplicating(app: ToonApp) -> None:
    _register_view(app, "alpha")
    _register_view(app, "beta")

    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()

        app.open_view("alpha")
        await pilot.pause()
        app.open_view("beta")
        await pilot.pause()
        assert app.query_one(ContentArea).active_name == "beta"

        # Re-opening the already-open view activates its tab, no duplicate.
        app.open_view("alpha")
        await pilot.pause()

        content = app.query_one(ContentArea)
        assert content.active_name == "alpha"
        assert content.open_names == frozenset({"alpha", "beta"})
        assert len(app.query(TabPane)) == 2
        assert len(app.query("#body-alpha")) == 1


async def test_two_views_coexist(app: ToonApp) -> None:
    _register_view(app, "alpha")
    _register_view(app, "beta")

    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()

        app.open_view("alpha")
        await pilot.pause()
        app.open_view("beta")
        await pilot.pause()

        content = app.query_one(ContentArea)
        assert content.open_names == frozenset({"alpha", "beta"})
        assert content.active_name == "beta"
        assert len(app.query(TabPane)) == 2
        assert len(app.query("#body-alpha")) == 1
        assert len(app.query("#body-beta")) == 1


async def test_closing_a_view_destroys_its_widget(app: ToonApp) -> None:
    _register_view(app, "alpha")
    _register_view(app, "beta")

    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()

        app.open_view("alpha")
        await pilot.pause()
        app.open_view("beta")
        await pilot.pause()

        app.close_view("beta")
        await pilot.pause()

        content = app.query_one(ContentArea)
        assert content.open_names == frozenset({"alpha"})
        assert content.active_name == "alpha"
        assert len(app.query("#body-beta")) == 0
        assert len(app.query("#body-alpha")) == 1

        app.close_view("alpha")
        await pilot.pause()

        assert content.open_names == frozenset()
        assert content.active_name is None
        assert len(app.query(TabPane)) == 0
        assert content.query_one("#view-empty", Static).display is True


async def test_reset_closes_every_view(app: ToonApp) -> None:
    _register_view(app, "alpha")
    _register_view(app, "beta")

    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()

        app.open_view("alpha")
        await pilot.pause()
        app.open_view("beta")
        await pilot.pause()

        app.reset_views()
        await pilot.pause()

        content = app.query_one(ContentArea)
        assert content.open_names == frozenset()
        assert content.active_name is None
        assert len(app.query(TabPane)) == 0
        assert len(app.query("#body-alpha")) == 0
        assert len(app.query("#body-beta")) == 0
        assert content.query_one("#view-empty", Static).display is True


async def test_a_command_can_open_a_view(app: ToonApp, submit: SubmitLine) -> None:
    _register_view(app, "alpha", title="Alpha")

    def show(ctx: CommandContext) -> str:
        ctx.host.open_view("alpha")
        return "opened alpha"

    app.registry.register_command(Command("show_alpha", show, "Open alpha."))

    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()

        await submit(app, pilot, "show_alpha")

        content = app.query_one(ContentArea)
        assert content.open_names == frozenset({"alpha"})
        assert len(app.query("#body-alpha")) == 1
