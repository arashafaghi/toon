# Toon architecture

## 1. Scope and status

This document records the agreed interfaces and repository layout for **M0** of
`roadmap.md`. Toon is an **architecture proof, not a general plugin framework**.

Plugins are **trusted, in-process Python**. There is no hot reload, no sandbox,
no process isolation, and no entry-point discovery. Anything beyond loading
local directories by convention is a follow-up, not part of this milestone.

## 2. Technology and build configuration

- Python **>=3.13**, pinned in `.python-version` (`3.13`).
- Runtime dependencies: **`textual`**, **`pydantic`**, and **`httpx`**.
- Dev dependencies: **`pytest`**, **`pytest-asyncio`**, **`ruff`**.
- Build backend: **`uv_build`**.
- Console script: **`toon = toon.app:main`**.

The runtime/extension API deliberately keeps Textual types at the UI boundary;
`toon.api.extension` only references them under `TYPE_CHECKING`.

## 3. Repository layout

```text
src/toon/app.py              # Textual app + entry point            (M1)
src/toon/api/extension.py    # public extension API (frozen)
src/toon/runtime/registry.py     # command/UI registry            (M1/M2)
src/toon/runtime/dispatcher.py   # parse + dispatch commands       (M1/M2)
src/toon/runtime/plugin_loader.py# discover + load plugins          (M1/M2)
src/toon/ui/repl.py          # interactive REPL                      (M1/M3)
src/toon/ui/content.py       # tabbed view host (content area)
plugins/<name>/plugin.py     # one directory per plugin
tests/                       # automated tests                       (M1+)
docs/architecture.md         # this document
```

## 4. Plugin entry point

- Each **immediate child directory of `plugins/`** that contains a `plugin.py`
  is one plugin candidate.
- The loader imports that module and calls its module-level function:

```python
def register(registry: ExtensionRegistry) -> None:
    ...
```

- The **plugin name is the directory name**.
- Discovery order is **sorted directory names** (deterministic).
- Do **not** recursively scan for Python files. Directories without a
  `plugin.py` are ignored.

## 5. Public API (frozen)

Everything below is defined in `src/toon/api/extension.py` and re-exported from
`toon.api`. Changing any of it requires an architecture update here first.

- **`RegistrationError(Exception)`** — raised when a command, screen, or widget
  cannot be registered (duplicate or invalid name); messages are user-facing.
- **`ScreenFactory = Callable[[], Screen]`** — returns a fresh Textual screen.
- **`WidgetFactory = Callable[[], Widget]`** — returns a fresh Textual widget.
- **`ViewHost`** (runtime-checkable `Protocol`) — host navigation injected into
  handlers:
  - `open_view(name: str) -> None` — open a widget contribution as a **tab**,
    or activate it if it is already open
  - `close_view(name: str) -> None` — close/destroy an open view
  - `open_screen(name: str) -> None`
  - `clear_output() -> None` (used by the built-in `clear` command)
  - `reset_views() -> None` (used by the built-in `reset` command; closes every
    view and screen)
- **`CommandContext`** (frozen, slotted dataclass):
  - `args: tuple[str, ...]`
  - `host: ViewHost`
- **`CommandHandler = Callable[[CommandContext], "str | None | Awaitable[str | None]"]`**
- **`Command`** (frozen, slotted dataclass):
  - `name: str`
  - `handler: CommandHandler`
  - `description: str = ""`
- **`CommandResult`** (frozen, slotted dataclass):
  - `command: str`
  - `output: str = ""`
  - `error: str | None = None`
  - property `ok -> bool` (``True`` when `error is None`)
- **`logger`** — the shared Loguru logger (`from toon.api import logger`);
  records are rendered in the REPL output area (see §10).
- **`ExtensionRegistry`** (runtime-checkable `Protocol`):

```python
def register_command(self, command: Command) -> None: ...
def register_screen(
    self, name: str, factory: ScreenFactory, *, description: str = ""
) -> None: ...
def register_widget(
    self,
    name: str,
    factory: WidgetFactory,
    *,
    description: str = "",
    title: str | None = None,
) -> None: ...
def register_header_item(
    self, name: str, factory: WidgetFactory, *, description: str = "",
    order: int = 0, view: str | None = None,
) -> None: ...
def register_footer_item(
    self, name: str, factory: WidgetFactory, *, description: str = "",
    order: int = 0, view: str | None = None,
) -> None: ...
```

Header/footer items are widgets the host renders **in its own bars** (lower
``order`` first); they never let a plugin touch host DOM. With ``view`` set the
item is shown only while that view is open (so it also disappears on ``reset``);
with ``view=None`` it lives for the whole session.

`title` is the label shown for the view's tab when it is opened; it defaults to
`name`. Duplicate or invalid names raise `RegistrationError`.

### Reusable UI widgets (`toon.api.widgets`)

Plugins that need an animated flow can reuse the host's widgets instead of
re-implementing the animation machinery. They live in `toon/api/widgets.py` and
are re-exported lazily (so `import toon.api` never imports Textual):

- **`render_track(phase, direction, length) -> str`** — pure helper returning a
  single horizontal track frame (a `▶`/`◀` arrow among dots).
- **`FlowTrack`** — a `Static` that animates the arrow. Options: `length`,
  `mode` (`"ping-pong"`/`"one-way"`), `duration`, `traversals`. It owns
  `start`/`pause`/`resume`/`restart`, exposes `is_done`, calls `on_finished`, and
  repaints only when the frame changes.
- **`FlowLane`** — a labelled row (name + source task + `FlowTrack` + sink task)
  that delegates control to its track and posts `FlowLane.Finished`.
- **`render_edge(phase, length, *, orientation, direction, ...) -> str`** — pure
  helper returning a wire frame with a travelling glow (a single line, or one
  line per row when vertical).
- **`FlowEdge`** — a `Static` drawing a dashed **wire** with a bright **pulse**
  travelling along it, one-way and repeating (like a packet on a cable). Options:
  `length`, `orientation` (`"horizontal"`/`"vertical"`), `direction`, `duration`,
  `traversals` (`None` loops forever), and the `wire`/`packet`/`trail` glyphs.
  It owns `start`/`pause`/`resume`/`restart`, `is_done`, and `on_finished`.
- **`Spinner`** — a one-line busy indicator with built-in Unicode and ASCII
  presets (default: the rotating braille dots `⣾⣽⣻⢿⡿⣟⣯⣷`) and an optional
  label. It mounts hidden; `start("Fetching…")` reveals and animates it, and
  `stop()` freezes and hides it. Pick a preset with `Spinner(preset="z_arrow")`,
  pass custom `frames=`, or switch at runtime with `set_preset()`; all names and
  frames are in `SPINNER_PRESETS`. `braille_random` picks a random braille
  character each tick. The REPL uses one while an async command runs.

### HTTP client (`toon.api.http`)

Plugins call external APIs (Jenkins, Gerrit, `~/.netrc` services, ...) with an
async, httpx-based client. It is re-exported lazily, so `import toon.api` never
imports httpx:

```python
from toon.api import BasicAuth, HttpClient

async with HttpClient("https://ci.example.com", auth=BasicAuth(user, token)) as api:
    data = await api.get_json("/api/json")
```

- **`HttpClient(base_url, *, auth=None, headers=None, timeout=..., follow_redirects=True, raise_for_status=True, transport=None)`**
  — an async context manager (also `aclose()`); `get/post/put/patch/delete/request`
  return a small **`HttpResponse`** (`status_code`, `headers`, `text`, `.json()`,
  `.ok`); `get_json`/`post_json` parse JSON. Non-2xx raises **`HttpError`** by
  default (`raise_for_status=False` to inspect instead).
- **Auth is a separate, pluggable class** implementing the `Auth` protocol
  (`async def apply(request) -> None`): **`BasicAuth`** (Jenkins user+token,
  Gerrit user+password), **`BearerAuth`**, **`HeaderAuth`** (API keys),
  **`NetrcAuth`** (per-host credentials from `~/.netrc`), and **`NoAuth`**
  (default). Swap one for another without touching request code.

## 6. Command execution conventions

- Tokenization uses **`shlex.split`**. No shell expansion, pipes, or chaining.
  **Empty input does nothing.**
- A handler receives one `CommandContext` and may be **sync or async**; the
  dispatcher normalises both and always returns a `CommandResult`.
- Handlers return **`str`** (output text) or **`None`** (no output). Handlers
  **never write to the REPL directly**.
- **`help` is generated from registered commands**, not a hardcoded list.
  Built-in **`help`**, **`clear`**, **`plugins`**, **`echo`**, and **`reset`**
  commands are registered by the host at startup.
- Unknown commands and invalid input produce a `CommandResult` with an `error`
  message and must **never crash the app**.

## 7. UI contribution conventions

- A screen contribution is a factory returning a fresh `textual.screen.Screen`;
  a widget contribution is a factory returning a fresh `textual.widget.Widget`.
  Factories are called on demand and **never return an already-mounted object**.
- The **host owns the `App`, the layout, and the REPL lifetime**.
- Plugin navigation goes through `CommandContext.host`
  (`open_screen` / `open_view` / `close_view`) — this is the **only navigation
  mechanism**; do not add a second one.
- Layout/navigation arrangement: the base screen holds a **persistent, tabbed
  content area above the REPL**. `open_view(name)` shows a widget contribution in
  its own **tab** — activating it if already open, with the tab label taken from
  the registration `title` — so several views can be open at once while the REPL
  stays usable. `close_view(name)` (or the host `ctrl+w` binding) **destroys** the
  view's widget; `reset_views()` closes them all. Screen contributions are
  **pushed onto the Textual screen stack** and **`Escape` pops back** to the REPL.
  The REPL lives on the base screen and is **never destroyed**.
- The base screen is framed by two **host-owned** bars: a header
  (`toon/ui/header.py`) with the title, plugin header items, and a live clock,
  and a footer (`toon/ui/footer.py`) listing every visible key binding, the
  command-palette hint, and plugin footer items. Add a shortcut simply by adding
  a `Binding(..., show=True)` to `ToonApp.BINDINGS`; plugins add widgets to a bar
  with `register_header_item` / `register_footer_item` — ordered, session-wide by
  default or shown only while a given `view=` is open. Further host
  segments/hints via `AppHeader.build_segments` and `AppFooter.EXTRA_HINTS`.

### Command-to-view mechanism (worked example)

The mechanism is: a command handler calls `ctx.host` — nothing else. There is no
second navigation path, and the host never special-cases a plugin name.

```python
# plugins/ui_demo/plugin.py (reference UI extension, M3)
def register(registry: ExtensionRegistry) -> None:
    registry.register_widget(
        "demo_widget", make_demo_widget, description="...", title="UI demo"
    )
    registry.register_screen("demo_screen", make_demo_screen, description="...")
    registry.register_command(Command("demo_widget", demo_widget, "Show the widget."))
    registry.register_command(Command("demo_screen", demo_screen, "Open the screen."))


def demo_widget(ctx: CommandContext) -> str:
    ctx.host.open_view("demo_widget")   # -> opened in its own tab
    return "Opened the 'demo_widget' view in a tab."


def demo_screen(ctx: CommandContext) -> str:
    ctx.host.open_screen("demo_screen")   # -> pushed; Escape returns to the REPL
    return "Opened the 'demo_screen' view. Press Escape to return to the REPL."
```

- `open_view(name)` calls the registered factory for a **fresh** widget and opens
  it in a new **tab** (or activates it if already open). `close_view(name)`
  destroys an open view; the host binds `ctrl+w` to close the active tab.
- `open_screen(name)` calls the registered factory for a **fresh** screen and
  pushes it; `Escape` (host binding) pops it, returning to the REPL.
- An unknown `name` surfaces as a normal `CommandResult` error, not a crash.

## 8. Failure handling

- Per-plugin import/registration errors are caught around `register()`, reported
  with the **plugin name and exception context**, and must **not stop later
  plugins from loading**.
- The dispatcher catches handler exceptions and turns them into
  `CommandResult.error`.
- No broad silent swallowing.

## 9. Delegation map / ownership

| Owner      | Files                                                             |
| ---------- | ----------------------------------------------------------------- |
| Agent A    | `src/toon/runtime/registry.py`, `src/toon/runtime/dispatcher.py`  |
| Agent B    | `src/toon/runtime/plugin_loader.py`, `plugins/`                   |
| Agent C    | `src/toon/ui/repl.py`, `src/toon/ui/content.py`                   |
| Integrator | `src/toon/app.py`, `pyproject.toml`, `src/toon/api/`, `README.md`, final integration |

## 10. Logging

Logging uses **Loguru**. Plugins log through the public API:

```python
from toon.api import logger

logger.info("widget opened for {}", name)
```

At startup the host (`toon.ui.logging`) *replaces Loguru's default stderr sink*
with a sink that renders each record into the REPL output area
(`#repl-log`) using Loguru's full default line
(`time | level | name:function:line - message`), coloured by level. So host and
plugin logs land in the same place you type commands.

Details:

- Records emitted **before the REPL is mounted** (plugins are imported and
  registered during `ToonApp.__init__`) are **buffered** and flushed on mount.
- Records emitted from a **non-UI thread** are marshalled onto the UI thread
  (`call_from_thread`), so sinks are safe to use from workers.
- The sink never raises into the caller; a failing write is swallowed.
- Level and format live in `toon/ui/logging.py` (`LOG_LEVEL`, `LOG_FORMAT`).

## 11. Session state ("memory")

The host remembers which views were open and reopens them on the next start.
State lives in a small JSON file (`toon/runtime/state.py`):

- Location: `$XDG_CONFIG_HOME/toon/state.json` (often
  `~/.config/toon/state.json`), overridable with the `TOON_STATE_FILE`
  environment variable or the `ToonApp(state_path=...)` argument.
- The file is **optional**: if it is missing it is created empty, and an
  unreadable/corrupt file degrades to an empty state (never blocks startup).
- The app writes the currently-open view names (in open order) whenever the set
  changes — on `open_view`, `close_view`, and `reset_views` — and restores them
  after mount, skipping names that are no longer registered.
- The same file also stores `history`: the last 20 REPL commands (oldest first),
  written on each submit. In the REPL, **Up/Down** walk that history with
  **prefix matching** (like bash's `history-search-backward` /
  `history-search-forward`): typing a prefix and pressing Up cycles only through
  past commands starting with it; Down returns to the draft.
