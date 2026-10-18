"""Nox sessions for the `toon` project.

Every session shells out to `uv run <tool>` so that the tooling and its
dependencies come from the project's uv-managed environment instead of a
virtualenv created by nox (`venv_backend="none"`).

Run `nox` with no arguments to execute the full `check` suite.
"""

from __future__ import annotations

import nox

nox.options.default_venv_backend = "none"
nox.options.sessions = ["check"]


@nox.session
def lint(session: nox.Session) -> None:
    """Run the ruff linter over the whole repository."""
    session.run("uv", "run", "ruff", "check", ".")


@nox.session
def format(session: nox.Session) -> None:
    """Check that the code is formatted with `ruff format`."""
    session.run("uv", "run", "ruff", "format", "--check", ".")


@nox.session
def type(session: nox.Session) -> None:
    """Run the mypy static type checker."""
    session.run("uv", "run", "mypy")


@nox.session
def test(session: nox.Session) -> None:
    """Run the test suite with pytest."""
    session.run("uv", "run", "pytest")


@nox.session
def check(session: nox.Session) -> None:
    """Run every quality gate: lint, format, type, then test."""
    session.notify("lint")
    session.notify("format")
    session.notify("type")
    session.notify("test")


@nox.session
def fix(session: nox.Session) -> None:
    """Auto-format the code and apply ruff's safe autofixes."""
    session.run("uv", "run", "ruff", "format", ".")
    session.run("uv", "run", "ruff", "check", "--fix", ".")
