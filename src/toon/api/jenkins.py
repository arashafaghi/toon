"""The data contract between the monitoring UI and a Jenkins data source.

The UI imports only these models and the :class:`JenkinsProvider` protocol.
Development fixtures and the real work adapter both translate their data into
these types, so the view never needs to know which one is in use.

Jenkins-specific API details (URLs, credentials, JSON shapes) stay in the
provider implementation, outside the UI and outside the public repository.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol, runtime_checkable

__all__ = [
    "BuildStatus",
    "JenkinsBuild",
    "JenkinsJob",
    "JenkinsProvider",
    "JenkinsProviderError",
]


class BuildStatus(StrEnum):
    """Normalised status of a Jenkins build."""

    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    RUNNING = "RUNNING"
    ABORTED = "ABORTED"
    UNSTABLE = "UNSTABLE"
    NOT_BUILT = "NOT_BUILT"
    UNKNOWN = "UNKNOWN"


class JenkinsProviderError(Exception):
    """Raised when a provider cannot list jobs or return a build.

    The message is shown in the UI, so it must be safe to display: no
    credentials, tokens, or internal endpoints.
    """


@dataclass(frozen=True, slots=True)
class JenkinsBuild:
    """One build of a Jenkins job, normalised into the UI's vocabulary.

    ``started_at`` should be timezone-aware (UTC is the usual choice).
    ``duration_seconds`` may be ``None`` while a build is still running or when
    the source does not report it.
    """

    number: int
    status: BuildStatus
    url: str = ""
    started_at: datetime | None = None
    duration_seconds: float | None = None


@dataclass(frozen=True, slots=True)
class JenkinsJob:
    """A Jenkins job and its latest build, if it has ever built.

    ``latest_build`` is ``None`` for jobs that have never produced a build.
    """

    name: str
    latest_build: JenkinsBuild | None = None
    url: str = ""


@runtime_checkable
class JenkinsProvider(Protocol):
    """The read-only data source the monitoring UI depends on.

    Implementations perform their own I/O and may cache. They should translate
    Jenkins results into the models above instead of exposing raw API data.
    """

    async def list_jobs(self) -> Sequence[JenkinsJob]:
        """Return every visible job, including jobs with no builds.

        Raises:
            JenkinsProviderError: if the job list cannot be fetched.
        """
        ...

    async def get_build(self, job_name: str, build_number: int) -> JenkinsBuild:
        """Return one build of ``job_name`` by its build number.

        Raises:
            JenkinsProviderError: if the job or build cannot be fetched.
        """
        ...
