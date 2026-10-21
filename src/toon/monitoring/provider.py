"""Select the Jenkins data source used by the monitoring UI.

For now the only implementation is the fixture provider. Keeping selection in
one function gives the work integration a single place to plug in the real
adapter later without changing the UI.
"""

from __future__ import annotations

import os

from toon.api import JenkinsProvider
from toon.monitoring.fixtures import FixtureJenkinsProvider

__all__ = [
    "FIXTURE_DELAY_ENV",
    "FIXTURE_ENV",
    "get_jenkins_provider",
]

#: Fixture scenario: ``default``, ``empty``, or ``error``.
FIXTURE_ENV = "TOON_JENKINS_FIXTURE"
#: Optional artificial delay, in seconds, added to each fixture request.
FIXTURE_DELAY_ENV = "TOON_JENKINS_FIXTURE_DELAY"


def get_jenkins_provider() -> JenkinsProvider:
    """Return the Jenkins provider configured for this process.

    Reads ``TOON_JENKINS_FIXTURE`` (default: ``default``) and
    ``TOON_JENKINS_FIXTURE_DELAY`` (default: ``0``). Invalid values raise
    ``ValueError`` so local setup mistakes are visible immediately.
    """
    scenario = os.environ.get(FIXTURE_ENV, "default").strip() or "default"
    delay = _fixture_delay()
    return FixtureJenkinsProvider(scenario=scenario, delay=delay)


def _fixture_delay() -> float:
    """Parse the optional fixture delay, with a clear error for bad values."""
    raw = os.environ.get(FIXTURE_DELAY_ENV, "").strip()
    if not raw:
        return 0.0
    try:
        return float(raw)
    except ValueError:
        raise ValueError(f"{FIXTURE_DELAY_ENV} must be a number of seconds, got {raw!r}") from None
