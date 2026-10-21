"""Jenkins monitoring view: jobs, latest build status, and build details.

The view talks only to the public :class:`~toon.api.JenkinsProvider` contract.
It asks :func:`~toon.api.get_jenkins_provider` for an implementation, so the same
UI works with the committed fixtures at home and the real work adapter later.

Open it with the ``jenkins`` command. The Refresh button reloads the job list;
moving through the table selects a job and fetches its latest build details.
"""

from __future__ import annotations

from datetime import datetime

from rich.markup import escape
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, DataTable, Static

from toon.api import (
    BuildStatus,
    Command,
    CommandContext,
    ExtensionRegistry,
    JenkinsBuild,
    JenkinsJob,
    JenkinsProvider,
    JenkinsProviderError,
    Spinner,
    get_jenkins_provider,
)

WIDGET_NAME = "jenkins"

_STATUS_COLOURS: dict[BuildStatus, str] = {
    BuildStatus.SUCCESS: "#3fb950",
    BuildStatus.FAILURE: "#f85149",
    BuildStatus.RUNNING: "#d29922",
    BuildStatus.UNSTABLE: "#d29922",
    BuildStatus.ABORTED: "#8b949e",
    BuildStatus.NOT_BUILT: "#8b949e",
    BuildStatus.UNKNOWN: "#8b949e",
}


class JenkinsView(Vertical):
    """A job table on the left and the selected build's details on the right."""

    DEFAULT_CSS = """
    JenkinsView {
        height: 1fr;
        padding: 0 1;
    }
    JenkinsView .title {
        color: #58a6ff;
        text-style: bold;
        height: 1;
    }
    JenkinsView #jenkins-toolbar {
        height: 1;
        align-vertical: middle;
    }
    JenkinsView #jenkins-spinner {
        width: auto;
        margin-right: 1;
    }
    JenkinsView #jenkins-status {
        width: 1fr;
        height: 1;
        content-align: left middle;
        color: #8b949e;
    }
    JenkinsView #jenkins-refresh {
        min-width: 10;
        height: 1;
        padding: 0 1;
        border: none;
    }
    JenkinsView #jenkins-body {
        height: 1fr;
    }
    JenkinsView #jenkins-jobs {
        width: 3fr;
        height: 1fr;
        background: #0d1117;
    }
    JenkinsView #jenkins-detail-panel {
        width: 2fr;
        height: 1fr;
        padding: 0 1;
        border-left: solid #30363d;
    }
    JenkinsView #jenkins-detail {
        height: auto;
    }
    """

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._provider: JenkinsProvider | None = None
        self._row_jobs: dict[str, JenkinsJob] = {}
        self._selected: tuple[str, int | None] | None = None
        self._jobs_generation = 0
        self._detail_generation = 0

    def compose(self) -> ComposeResult:
        """Lay out the toolbar, job table, and build-detail panel."""
        yield Static("Jenkins monitoring", classes="title")
        with Horizontal(id="jenkins-toolbar"):
            yield Spinner(id="jenkins-spinner")
            yield Static("Starting…", id="jenkins-status")
            yield Button("Refresh", id="jenkins-refresh", variant="primary")
        with Horizontal(id="jenkins-body"):
            yield DataTable(
                zebra_stripes=True,
                cursor_type="row",
                id="jenkins-jobs",
            )
            with VerticalScroll(id="jenkins-detail-panel"):
                yield Static("Select a job to inspect its latest build.", id="jenkins-detail")

    def on_mount(self) -> None:
        """Set up the table after the view's children are mounted."""
        self.call_after_refresh(self._start)

    def _start(self) -> None:
        """Create the table columns and load the first job list."""
        if not self.is_mounted:
            return
        table = self.query_one(DataTable)
        table.add_columns("Job", "Build", "Status", "Started")
        self._load()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Reload the job list on Refresh."""
        event.stop()
        if event.button.id == "jenkins-refresh":
            self._load()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Show details when the user moves to another job row."""
        if event.data_table.id != "jenkins-jobs":
            return
        job = self._row_jobs.get(str(event.row_key.value))
        if job is not None:
            self._select_job(job)

    # --- loading -----------------------------------------------------------

    def _load(self) -> None:
        """Clear the current data and fetch jobs through the provider."""
        table = self.query_one(DataTable)
        table.clear()
        self._row_jobs.clear()
        self._provider = None
        self._selected = None
        self._jobs_generation += 1
        generation = self._jobs_generation
        self._detail_generation += 1
        self.workers.cancel_group(self, "jenkins-detail")
        self._set_detail("[dim]Select a job to inspect its latest build.[/dim]")
        self.query_one(Spinner).start("Loading jobs…")
        self.query_one("#jenkins-status", Static).update("[yellow]Loading jobs…[/yellow]")
        self.run_worker(
            self._fetch_jobs(generation),
            exclusive=True,
            group="jenkins-jobs",
        )

    async def _fetch_jobs(self, generation: int) -> None:
        """Fetch and render the job list, turning failures into readable text."""
        try:
            provider = get_jenkins_provider()
            jobs = tuple(await provider.list_jobs())
        except JenkinsProviderError as exc:
            if generation == self._jobs_generation and self.is_mounted:
                self._show_error(f"Jenkins error: {exc}")
        except ValueError as exc:
            if generation == self._jobs_generation and self.is_mounted:
                self._show_error(str(exc))
        except Exception as exc:  # noqa: BLE001 - a provider bug must not crash the view
            if generation == self._jobs_generation and self.is_mounted:
                self._show_error(f"{type(exc).__name__}: {exc}")
        else:
            if generation == self._jobs_generation and self.is_mounted:
                self._provider = provider
                self._populate(jobs)
        finally:
            if generation == self._jobs_generation and self.is_mounted:
                self.query_one(Spinner).stop()

    def _populate(self, jobs: tuple[JenkinsJob, ...]) -> None:
        """Add every job to the table and select the first one."""
        table = self.query_one(DataTable)
        self._row_jobs.clear()
        for index, job in enumerate(jobs):
            key = str(index)
            self._row_jobs[key] = job
            build = job.latest_build
            table.add_row(
                Text(job.name),
                Text(f"#{build.number}" if build is not None else "—"),
                _status_cell(build.status if build is not None else None),
                Text(_format_started(build.started_at) if build is not None else "—"),
                key=key,
            )

        status = self.query_one("#jenkins-status", Static)
        if not jobs:
            status.update("No jobs found.")
            self._set_detail("[dim]No Jenkins jobs are available.[/dim]")
            return

        suffix = "" if len(jobs) == 1 else "s"
        status.update(f"{len(jobs)} job{suffix} loaded.")
        table.move_cursor(row=0)
        self._select_job(jobs[0])

    def _show_error(self, message: str) -> None:
        """Show a provider/configuration error in the status line and details."""
        safe = escape(message)
        self.query_one("#jenkins-status", Static).update(f"[red]{safe}[/red]")
        self._set_detail(f"[red]{safe}[/red]")
        self.query_one(DataTable).clear()
        self._row_jobs.clear()
        self._selected = None

    # --- build details -----------------------------------------------------

    def _select_job(self, job: JenkinsJob) -> None:
        """Fetch or render the selected job's latest build."""
        build = job.latest_build
        key = (job.name, build.number if build is not None else None)
        if key == self._selected:
            return
        self._selected = key

        if build is None:
            self._detail_generation += 1
            self.workers.cancel_group(self, "jenkins-detail")
            self._set_detail(_no_build_text(job))
            return

        provider = self._provider
        if provider is None:
            self._set_detail("[red]No provider is available.[/red]")
            return

        self._detail_generation += 1
        generation = self._detail_generation
        self._set_detail(f"[dim]Loading build #{build.number}…[/dim]")
        self.run_worker(
            self._fetch_build(provider, job, build.number, generation),
            exclusive=True,
            group="jenkins-detail",
        )

    async def _fetch_build(
        self,
        provider: JenkinsProvider,
        job: JenkinsJob,
        build_number: int,
        generation: int,
    ) -> None:
        """Fetch one build and render it unless the selection has moved on."""
        try:
            build = await provider.get_build(job.name, build_number)
        except JenkinsProviderError as exc:
            if generation == self._detail_generation and self.is_mounted:
                self._set_detail(_error_text(f"Jenkins error: {exc}"))
            return
        except Exception as exc:  # noqa: BLE001 - keep the view usable
            if generation == self._detail_generation and self.is_mounted:
                self._set_detail(_error_text(f"{type(exc).__name__}: {exc}"))
            return
        if generation == self._detail_generation and self.is_mounted:
            self._set_detail(_build_text(job, build))

    def _set_detail(self, markup: str) -> None:
        """Replace the build-detail panel contents."""
        self.query_one("#jenkins-detail", Static).update(markup)


# --- formatting ------------------------------------------------------------


def _status_cell(status: BuildStatus | None) -> Text:
    """Return a coloured table cell for a build status."""
    if status is None:
        return Text("no builds", style="dim")
    return Text(status.value, style=_STATUS_COLOURS[status])


def _format_started(started_at: datetime | None) -> str:
    """Format a build start time, preserving its source timezone."""
    if started_at is None:
        return "—"
    if started_at.tzinfo is None:
        return started_at.strftime("%Y-%m-%d %H:%M")
    return started_at.strftime("%Y-%m-%d %H:%M %Z")


def _format_duration(seconds: float | None, status: BuildStatus) -> str:
    """Format a build duration, or describe a build that is still running."""
    if seconds is None:
        return "still running" if status is BuildStatus.RUNNING else "—"
    total = max(0, int(seconds))
    minutes, remainder = divmod(total, 60)
    return f"{minutes}m {remainder}s" if minutes else f"{remainder}s"


def _build_text(job: JenkinsJob, build: JenkinsBuild) -> str:
    """Render a build's details as safe Rich markup."""
    colour = _STATUS_COLOURS.get(build.status, "#8b949e")
    lines = [
        f"[bold]{escape(job.name)}[/bold]",
        "",
        f"Build:    #{build.number}",
        f"Status:   [{colour}]{escape(build.status.value)}[/]",
        f"Started:  {escape(_format_started(build.started_at))}",
        f"Duration: {escape(_format_duration(build.duration_seconds, build.status))}",
    ]
    if build.url:
        lines.append(f"URL:      {escape(build.url)}")
    return "\n".join(lines)


def _no_build_text(job: JenkinsJob) -> str:
    """Render the details panel for a job that has never built."""
    lines = [f"[bold]{escape(job.name)}[/bold]", "", "No builds yet."]
    if job.url:
        lines.append(f"Job URL:  {escape(job.url)}")
    return "\n".join(lines)


def _error_text(message: str) -> str:
    """Render a provider/detail error as safe Rich markup."""
    return f"[red]{escape(message)}[/red]"


# --- registration ----------------------------------------------------------


def make_jenkins_view() -> JenkinsView:
    """Return a *fresh* view instance on every call."""
    return JenkinsView()


def open_jenkins(ctx: CommandContext) -> str:
    """Open the Jenkins monitoring view as a tab."""
    ctx.host.open_view(WIDGET_NAME)
    return "Opened Jenkins monitoring. Use Refresh to reload the job list."


def register(registry: ExtensionRegistry) -> None:
    """Register the monitoring view and its command."""
    registry.register_widget(
        WIDGET_NAME,
        make_jenkins_view,
        description="Jenkins jobs, latest build status, and build details.",
        title="Jenkins",
    )
    registry.register_command(Command("jenkins", open_jenkins, "Open the Jenkins monitoring view."))
