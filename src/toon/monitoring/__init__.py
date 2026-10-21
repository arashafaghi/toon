"""Jenkins monitoring data sources.

The UI depends on :class:`toon.api.JenkinsProvider` and asks
:func:`get_jenkins_provider` for an implementation. At home that is the fixture
provider; at work the same seam can return the private adapter.
"""

from toon.monitoring.fixtures import FixtureJenkinsProvider, FixtureScenario
from toon.monitoring.provider import (
    FIXTURE_DELAY_ENV,
    FIXTURE_ENV,
    get_jenkins_provider,
)

__all__ = [
    "FIXTURE_DELAY_ENV",
    "FIXTURE_ENV",
    "FixtureJenkinsProvider",
    "FixtureScenario",
    "get_jenkins_provider",
]
