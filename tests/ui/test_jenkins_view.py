"""Behavior tests for the bundled Jenkins monitoring view.

Every test drives :class:`toon.app.ToonApp` through Textual's headless pilot,
opens the view through the real ``jenkins`` command, and uses the fixture
provider selected by the public environment seam. Assertions are about what a
user sees: the job table, the selected build's details, and loading/error/empty
states. No plugin internals are called directly.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

import pytest
from textual.pilot import Pilot
from textual.widgets import Button, DataTable, Static, TabbedContent

from toon.api import Spinner
from toon.app import ToonApp
from toon.monitoring import FIXTURE_DELAY_ENV, FIXTURE_ENV
from toon.ui.content import ContentArea

SubmitLine = Callable[[ToonApp, Pilot[None], str], Awaitable[None]]


@pytest.fixture(autouse=True)
def _clean_jenkins_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep each test independent of any fixture settings in the environment."""
    monkeypatch.delenv(FIXTURE_ENV, raising=False)
    monkeypatch.delenv(FIXTURE_DELAY_ENV, raising=False)


async def _wait_until(
    pilot: Pilot[None],
    predicate: Callable[[], bool],
    *,
    timeout: float = 5.0,
) -> None:
    """Poll a visible condition while letting the app process messages."""
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > deadline:
            raise AssertionError("condition was not met before the timeout")
        await pilot.pause(0.01)


async def _open_jenkins(app: ToonApp, pilot: Pilot[None], submit: SubmitLine) -> None:
    """Run the real ``jenkins`` command and wait for the view to mount."""
    await submit(app, pilot, "jenkins")
    await _wait_until(pilot, lambda: len(app.query("#jenkins-status")) == 1)


def _table(app: ToonApp) -> DataTable:
    return app.query_one("#jenkins-jobs", DataTable)


def _status(app: ToonApp) -> str:
    return str(app.query_one("#jenkins-status", Static).render()).strip()


def _detail(app: ToonApp) -> str:
    return str(app.query_one("#jenkins-detail", Static).render())


def _rows(app: ToonApp) -> list[list[str]]:
    table = _table(app)
    return [[str(cell) for cell in table.get_row_at(index)] for index in range(table.row_count)]


async def _select_job(app: ToonApp, pilot: Pilot[None], name: str) -> None:
    """Move the table cursor to ``name`` and wait for its detail response."""
    table = _table(app)
    index = next(
        index for index in range(table.row_count) if str(table.get_row_at(index)[0]) == name
    )
    table.move_cursor(row=index)
    await pilot.pause()
    await _wait_until(
        pilot,
        lambda: name in _detail(app) and "Loading build" not in _detail(app),
    )


async def _click_refresh(app: ToonApp, pilot: Pilot[None]) -> None:
    """Click Refresh after its short press animation has finished."""
    button = app.query_one("#jenkins-refresh", Button)
    await _wait_until(pilot, lambda: not button.has_class("-active"))
    await pilot.click(button)


async def test_the_jenkins_command_opens_a_job_table_with_build_statuses(
    jenkins_app: ToonApp, submit: SubmitLine
) -> None:
    async with jenkins_app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await _open_jenkins(jenkins_app, pilot, submit)
        await _wait_until(pilot, lambda: _status(jenkins_app) == "6 jobs loaded.")
        await _wait_until(pilot, lambda: "api-service" in _detail(jenkins_app))

        assert jenkins_app.query_one(ContentArea).active_name == "jenkins"
        tab = jenkins_app.query_one(TabbedContent).get_tab("view-jenkins")
        assert tab.label_text == "Jenkins"

        assert {row[0]: row[2] for row in _rows(jenkins_app)} == {
            "api-service": "SUCCESS",
            "billing-worker": "FAILURE",
            "mobile-app": "RUNNING",
            "nightly-smoke": "UNSTABLE",
            "docs-site": "SUCCESS",
            "new-service": "no builds",
        }

        detail = _detail(jenkins_app)
        assert "api-service" in detail
        assert "#128" in detail
        assert "SUCCESS" in detail
        assert "3m 2s" in detail
        assert "https://ci.example.com/job/api-service/128/" in detail


async def test_selecting_jobs_updates_details_for_failed_running_and_unbuilt_jobs(
    jenkins_app: ToonApp, submit: SubmitLine
) -> None:
    async with jenkins_app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await _open_jenkins(jenkins_app, pilot, submit)
        await _wait_until(pilot, lambda: "api-service" in _detail(jenkins_app))

        await _select_job(jenkins_app, pilot, "billing-worker")
        detail = _detail(jenkins_app)
        assert "billing-worker" in detail
        assert "#77" in detail
        assert "FAILURE" in detail
        assert "1m 4s" in detail

        await _select_job(jenkins_app, pilot, "mobile-app")
        detail = _detail(jenkins_app)
        assert "mobile-app" in detail
        assert "#203" in detail
        assert "RUNNING" in detail
        assert "still running" in detail

        await _select_job(jenkins_app, pilot, "new-service")
        detail = _detail(jenkins_app)
        assert "new-service" in detail
        assert "No builds yet." in detail
        assert "https://ci.example.com/job/new-service/" in detail


async def test_loading_state_is_visible_until_the_provider_returns(
    jenkins_app: ToonApp, submit: SubmitLine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(FIXTURE_DELAY_ENV, "0.5")

    async with jenkins_app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await _open_jenkins(jenkins_app, pilot, submit)
        await _wait_until(pilot, lambda: _status(jenkins_app) == "Loading jobs…")

        spinner = jenkins_app.query_one("#jenkins-spinner", Spinner)
        assert spinner.is_spinning is True
        assert spinner.has_class("hidden") is False
        assert _table(jenkins_app).row_count == 0

        await _wait_until(pilot, lambda: _status(jenkins_app) == "6 jobs loaded.")

        assert spinner.is_spinning is False
        assert spinner.has_class("hidden") is True
        assert _table(jenkins_app).row_count == 6


async def test_empty_provider_result_is_shown_without_jobs(
    jenkins_app: ToonApp, submit: SubmitLine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(FIXTURE_ENV, "empty")

    async with jenkins_app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await _open_jenkins(jenkins_app, pilot, submit)
        await _wait_until(pilot, lambda: _status(jenkins_app) == "No jobs found.")

        assert _table(jenkins_app).row_count == 0
        assert "No Jenkins jobs are available." in _detail(jenkins_app)
        assert jenkins_app.query_one("#jenkins-spinner", Spinner).is_spinning is False


async def test_refresh_clears_stale_data_on_error_and_recovers(
    jenkins_app: ToonApp, submit: SubmitLine, monkeypatch: pytest.MonkeyPatch
) -> None:
    async with jenkins_app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await _open_jenkins(jenkins_app, pilot, submit)
        await _wait_until(pilot, lambda: _status(jenkins_app) == "6 jobs loaded.")
        assert _table(jenkins_app).row_count == 6

        monkeypatch.setenv(FIXTURE_ENV, "error")
        await _click_refresh(jenkins_app, pilot)
        await _wait_until(pilot, lambda: "Jenkins error:" in _status(jenkins_app))

        assert _table(jenkins_app).row_count == 0
        assert "unavailable" in _detail(jenkins_app)
        assert "api-service" not in _detail(jenkins_app)

        monkeypatch.setenv(FIXTURE_ENV, "default")
        await _click_refresh(jenkins_app, pilot)
        await _wait_until(pilot, lambda: _status(jenkins_app) == "6 jobs loaded.")
        await _wait_until(pilot, lambda: "api-service" in _detail(jenkins_app))

        assert _table(jenkins_app).row_count == 6
