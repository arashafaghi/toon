"""In-memory Jenkins data for developing the monitoring UI without a server.

All names, URLs, and numbers here are invented. The fixture provider implements
the public :class:`~toon.api.JenkinsProvider` protocol, so the UI can use it
exactly like the real work adapter.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime
from enum import StrEnum

from toon.api import BuildStatus, JenkinsBuild, JenkinsJob, JenkinsProviderError

__all__ = ["FixtureJenkinsProvider", "FixtureScenario"]

_BASE_URL = "https://ci.example.com"


class FixtureScenario(StrEnum):
    """The data shape a :class:`FixtureJenkinsProvider` should expose."""

    DEFAULT = "default"
    EMPTY = "empty"
    ERROR = "error"


def _build(
    job_name: str,
    number: int,
    status: BuildStatus,
    *,
    started_at: datetime,
    duration_seconds: float | None,
) -> JenkinsBuild:
    """Build an invented build with a consistent URL."""
    return JenkinsBuild(
        number=number,
        status=status,
        url=f"{_BASE_URL}/job/{job_name}/{number}/",
        started_at=started_at,
        duration_seconds=duration_seconds,
    )


def _job(name: str, latest_build: JenkinsBuild | None) -> JenkinsJob:
    """Build an invented job with a consistent URL."""
    return JenkinsJob(name=name, latest_build=latest_build, url=f"{_BASE_URL}/job/{name}/")


_DEFAULT_JOBS: tuple[JenkinsJob, ...] = (
    _job(
        "api-service",
        _build(
            "api-service",
            128,
            BuildStatus.SUCCESS,
            started_at=datetime(2026, 10, 22, 9, 12, tzinfo=UTC),
            duration_seconds=182.4,
        ),
    ),
    _job(
        "billing-worker",
        _build(
            "billing-worker",
            77,
            BuildStatus.FAILURE,
            started_at=datetime(2026, 10, 22, 9, 5, tzinfo=UTC),
            duration_seconds=64.8,
        ),
    ),
    _job(
        "mobile-app",
        _build(
            "mobile-app",
            203,
            BuildStatus.RUNNING,
            started_at=datetime(2026, 10, 22, 9, 28, tzinfo=UTC),
            duration_seconds=None,
        ),
    ),
    _job(
        "nightly-smoke",
        _build(
            "nightly-smoke",
            45,
            BuildStatus.UNSTABLE,
            started_at=datetime(2026, 10, 22, 3, 0, tzinfo=UTC),
            duration_seconds=421.0,
        ),
    ),
    _job(
        "docs-site",
        _build(
            "docs-site",
            12,
            BuildStatus.SUCCESS,
            started_at=datetime(2026, 10, 21, 17, 40, tzinfo=UTC),
            duration_seconds=38.2,
        ),
    ),
    _job("new-service", None),
)


class FixtureJenkinsProvider:
    """A deterministic, in-memory :class:`~toon.api.JenkinsProvider`.

    ``scenario`` selects the data shape:

    * ``"default"`` — successful, failed, running, unstable, and never-built jobs
    * ``"empty"`` — no jobs
    * ``"error"`` — every request raises :class:`JenkinsProviderError`

    ``delay`` adds an artificial wait (in seconds) to each request, which is
    useful for exercising the UI's loading state. It does not affect the data.
    """

    def __init__(
        self,
        *,
        scenario: FixtureScenario | str = FixtureScenario.DEFAULT,
        delay: float = 0.0,
    ) -> None:
        try:
            self._scenario = FixtureScenario(scenario)
        except ValueError:
            choices = ", ".join(item.value for item in FixtureScenario)
            raise ValueError(
                f"unknown fixture scenario {scenario!r}; choose from: {choices}"
            ) from None
        if delay < 0:
            raise ValueError("delay must be zero or greater")
        self._delay = delay
        self._jobs: tuple[JenkinsJob, ...] = (
            _DEFAULT_JOBS if self._scenario is FixtureScenario.DEFAULT else ()
        )

    @property
    def scenario(self) -> FixtureScenario:
        """The selected fixture scenario."""
        return self._scenario

    async def list_jobs(self) -> Sequence[JenkinsJob]:
        """Return the scenario's jobs, including jobs with no builds."""
        await self._wait()
        if self._scenario is FixtureScenario.ERROR:
            raise JenkinsProviderError("Jenkins is unavailable (fixture scenario).")
        return self._jobs

    async def get_build(self, job_name: str, build_number: int) -> JenkinsBuild:
        """Return the latest build when it matches ``build_number``."""
        await self._wait()
        if self._scenario is FixtureScenario.ERROR:
            raise JenkinsProviderError("Jenkins is unavailable (fixture scenario).")
        for job in self._jobs:
            build = job.latest_build
            if job.name == job_name and build is not None and build.number == build_number:
                return build
        raise JenkinsProviderError(f"Build {job_name} #{build_number} was not found.")

    async def _wait(self) -> None:
        """Apply the optional artificial request delay."""
        if self._delay:
            await asyncio.sleep(self._delay)
