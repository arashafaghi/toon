"""Behavior tests for the public Jenkins provider seam and fixture data.

These tests deliberately use the same entry point as the UI
(:func:`toon.api.get_jenkins_provider`) and talk only through
:class:`~toon.api.JenkinsProvider`. They describe the data behavior the
monitoring feature depends on rather than provider implementation details.
"""

from __future__ import annotations

import pytest

from toon.api import (
    BuildStatus,
    JenkinsProvider,
    JenkinsProviderError,
    get_jenkins_provider,
)
from toon.monitoring import FIXTURE_DELAY_ENV, FIXTURE_ENV


@pytest.fixture(autouse=True)
def _clean_jenkins_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep each test independent of any fixture settings in the environment."""
    monkeypatch.delenv(FIXTURE_ENV, raising=False)
    monkeypatch.delenv(FIXTURE_DELAY_ENV, raising=False)


async def test_default_provider_exposes_every_supported_build_outcome() -> None:
    provider = get_jenkins_provider()

    assert isinstance(provider, JenkinsProvider)
    jobs = await provider.list_jobs()
    by_name = {job.name: job for job in jobs}

    assert set(by_name) == {
        "api-service",
        "billing-worker",
        "mobile-app",
        "nightly-smoke",
        "docs-site",
        "new-service",
    }
    assert {job.latest_build.status for job in jobs if job.latest_build is not None} == {
        BuildStatus.SUCCESS,
        BuildStatus.FAILURE,
        BuildStatus.RUNNING,
        BuildStatus.UNSTABLE,
    }
    assert by_name["new-service"].latest_build is None
    assert all(job.url for job in jobs)


async def test_latest_builds_are_retrievable_by_job_name_and_number() -> None:
    provider = get_jenkins_provider()

    for job in await provider.list_jobs():
        latest = job.latest_build
        if latest is None:
            continue
        fetched = await provider.get_build(job.name, latest.number)
        assert fetched == latest


async def test_unknown_builds_raise_the_documented_provider_error() -> None:
    provider = get_jenkins_provider()

    with pytest.raises(JenkinsProviderError, match="missing #1"):
        await provider.get_build("missing", 1)

    with pytest.raises(JenkinsProviderError, match="api-service #999"):
        await provider.get_build("api-service", 999)


async def test_empty_scenario_returns_no_jobs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(FIXTURE_ENV, "empty")

    provider = get_jenkins_provider()

    assert list(await provider.list_jobs()) == []


async def test_error_scenario_fails_both_provider_operations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(FIXTURE_ENV, "error")

    provider = get_jenkins_provider()

    with pytest.raises(JenkinsProviderError, match="unavailable"):
        await provider.list_jobs()
    with pytest.raises(JenkinsProviderError, match="unavailable"):
        await provider.get_build("api-service", 128)


def test_invalid_scenario_is_rejected_with_a_helpful_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(FIXTURE_ENV, "staging")

    with pytest.raises(ValueError, match="unknown fixture scenario 'staging'"):
        get_jenkins_provider()


def test_invalid_delay_is_rejected_with_a_helpful_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(FIXTURE_DELAY_ENV, "soon")

    with pytest.raises(ValueError, match=FIXTURE_DELAY_ENV):
        get_jenkins_provider()
