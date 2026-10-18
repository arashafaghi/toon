"""GitHub demo plugin: call the GitHub API with the public HttpClient.

Shows the host's async HTTP client in action against a real service. The token
is read from the ``GITHUB_API`` environment variable at call time (never from
code), and supplied to the client via :class:`~toon.api.BearerAuth`.

Two ways to use it:

* **Commands** (results printed in the REPL): ``gh_me``, ``gh_repos``,
  ``gh_rate`` — these are async handlers, so the dispatcher awaits them.
* **A view** (``github`` command): a tab that fetches in a Textual worker and
  refreshes on demand.

Set the token first, e.g. ``export GITHUB_API=ghp_...`` (or a fine-grained
token), then run ``github`` / ``gh_me``.
"""

from __future__ import annotations

import os

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Static

from toon.api import (
    BearerAuth,
    Command,
    CommandContext,
    ExtensionRegistry,
    HttpClient,
    HttpError,
)

WIDGET_NAME = "github"

_TOKEN_ENV = "GITHUB_API"
_API = "https://api.github.com"
_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

_NO_TOKEN = (
    f"No GitHub token found. Set the {_TOKEN_ENV} environment variable to a "
    "GitHub personal access token and try again."
)


def _token() -> str | None:
    """Return the configured token, or ``None``."""
    token = os.environ.get(_TOKEN_ENV, "").strip()
    return token or None


def _client() -> HttpClient | None:
    """Build a GitHub client from the environment, or ``None`` if no token."""
    token = _token()
    if token is None:
        return None
    return HttpClient(_API, auth=BearerAuth(token), headers=_HEADERS, timeout=15.0)


# --- command handlers ------------------------------------------------------


async def gh_me(ctx: CommandContext) -> str:
    """Show the authenticated GitHub user."""
    client = _client()
    if client is None:
        return _NO_TOKEN
    try:
        async with client:
            user = await client.get_json("/user")
        name = user.get("name") or "no name"
        return (
            f"Signed in as {user.get('login')} ({name}) — "
            f"public repos: {user.get('public_repos', '?')}"
        )
    except HttpError as exc:
        return f"GitHub API error: {exc}"


async def gh_rate(ctx: CommandContext) -> str:
    """Show the GitHub core rate limit."""
    client = _client()
    if client is None:
        return _NO_TOKEN
    try:
        async with client:
            data = await client.get_json("/rate_limit")
        core = data["resources"]["core"]
        return f"Core rate limit: {core['remaining']}/{core['limit']} remaining."
    except HttpError as exc:
        return f"GitHub API error: {exc}"


async def gh_repos(ctx: CommandContext) -> str:
    """List the most recently updated repositories you can see."""
    client = _client()
    if client is None:
        return _NO_TOKEN
    try:
        async with client:
            repos = await client.get_json("/user/repos", params={"per_page": 5, "sort": "updated"})
        if not repos:
            return "No repositories found."
        return "\n".join(f"- {repo['full_name']}" for repo in repos)
    except HttpError as exc:
        return f"GitHub API error: {exc}"


def open_github(ctx: CommandContext) -> str:
    """Open the GitHub demo view as a tab."""
    ctx.host.open_view(WIDGET_NAME)
    return "Opened the GitHub view. Use Refresh to re-fetch."


# --- the view --------------------------------------------------------------


class GitHubView(Vertical):
    """A tab that fetches from GitHub in a worker and shows the result."""

    DEFAULT_CSS = """
    GitHubView {
        height: auto;
        padding: 1 2;
    }
    GitHubView #gh-body {
        height: auto;
    }
    GitHubView #gh-actions {
        height: auto;
        margin-top: 1;
    }
    """

    def compose(self) -> ComposeResult:
        """A body area and a refresh button."""
        yield Static("Loading…", id="gh-body")
        with Horizontal(id="gh-actions"):
            yield Button("Refresh", id="gh-refresh", variant="primary")

    def on_mount(self) -> None:
        """Fetch once when the view opens."""
        self._load()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Re-fetch on Refresh."""
        event.stop()
        if event.button.id == "gh-refresh":
            self._load()

    def _load(self) -> None:
        self.query_one("#gh-body", Static).update("Loading…")
        self.run_worker(self._fetch(), exclusive=True)

    async def _fetch(self) -> None:
        body = self.query_one("#gh-body", Static)
        client = _client()
        if client is None:
            body.update(f"[yellow]{_NO_TOKEN}[/yellow]")
            return
        try:
            async with client:
                user = await client.get_json("/user")
                rate = await client.get_json("/rate_limit")
                repos = await client.get_json(
                    "/user/repos", params={"per_page": 5, "sort": "updated"}
                )
        except HttpError as exc:
            body.update(f"[red]GitHub API error: {exc}[/red]")
            return
        except Exception as exc:  # network/DNS/timeout and friends
            body.update(f"[red]{type(exc).__name__}: {exc}[/red]")
            return

        core = rate["resources"]["core"]
        lines = [
            f"[bold]{user.get('login')}[/bold] ({user.get('name') or 'no name'})",
            f"public repos: {user.get('public_repos', '?')}   "
            f"rate limit: {core['remaining']}/{core['limit']}",
            "",
            "[bold]Recently updated:[/bold]",
        ]
        lines.extend(f"  - {repo['full_name']}" for repo in repos)
        body.update("\n".join(lines))


def make_github_view() -> GitHubView:
    """Return a *fresh* view instance on every call."""
    return GitHubView()


# --- header status badge ---------------------------------------------------

#: Seconds between authentication checks.
CHECK_INTERVAL = 30.0
_STATUS_COLOURS = {"ok": "#3fb950", "error": "#f85149", "missing": "#d29922"}
_STATUS_GLYPHS = {"ok": "●", "error": "●", "missing": "○"}


class GitHubStatus(Static):
    """Header item: ``github`` plus a coloured authentication-status glyph.

    ``state`` is ``"ok"`` (green, token works), ``"error"`` (red, auth/network
    failed), or ``"missing"`` (amber, no token configured). The tooltip carries
    the detail. It re-checks on an interval while its view is open.
    """

    DEFAULT_CSS = """
    GitHubStatus {
        width: auto;
        height: 1;
        content-align: center middle;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs: object) -> None:
        super().__init__("", **kwargs)
        self.state = "missing"
        self._checking = False

    def on_mount(self) -> None:
        """Render the initial state, check once, then poll."""
        self._render_state("missing")
        self._check()
        self.set_interval(CHECK_INTERVAL, self._check)

    def _render_state(self, state: str) -> None:
        self.state = state
        colour = _STATUS_COLOURS[state]
        glyph = _STATUS_GLYPHS[state]
        # Plain label + coloured status glyph (no filled background).
        self.update(f"github [bold {colour}]{glyph}[/]")

    def _check(self) -> None:
        if self._checking:
            return
        self._checking = True
        self.run_worker(self._verify(), exclusive=True)

    async def _verify(self) -> None:
        try:
            client = _client()
            if client is None:
                self._render_state("missing")
                self.tooltip = f"No token: set {_TOKEN_ENV}"
                return
            async with client:
                user = await client.get_json("/user")  # auth test
            self._render_state("ok")
            self.tooltip = f"Authenticated as {user.get('login')}"
        except HttpError as exc:
            self._render_state("error")
            self.tooltip = f"Auth failed: {exc}"
        except Exception as exc:  # network/DNS/timeout and friends
            self._render_state("error")
            self.tooltip = f"{type(exc).__name__}: {exc}"
        finally:
            self._checking = False


def make_github_status() -> GitHubStatus:
    """Return a *fresh* header status badge."""
    return GitHubStatus(id="gh-status")


def register(registry: ExtensionRegistry) -> None:
    """Register the GitHub view and commands."""
    registry.register_widget(
        WIDGET_NAME,
        make_github_view,
        description="GitHub API demo (needs the GITHUB_API token).",
        title="GitHub",
    )
    registry.register_header_item(
        "github_status",
        make_github_status,
        description="GitHub authentication status.",
        order=0,
        view=WIDGET_NAME,  # shown only while the GitHub view is open
    )
    registry.register_command(Command("github", open_github, "Open the GitHub API demo view."))
    registry.register_command(Command("gh_me", gh_me, "Show the authenticated GitHub user."))
    registry.register_command(Command("gh_repos", gh_repos, "List your recently updated repos."))
    registry.register_command(Command("gh_rate", gh_rate, "Show the GitHub API rate limit."))
