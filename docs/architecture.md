# Toon architecture

## 1. Scope and status

This document records the agreed interfaces and repository layout for **M0** of
`roadmap.md`. Toon is an **architecture proof, not a general plugin framework**.

Plugins are **trusted, in-process Python**. There is no hot reload, no sandbox,
no process isolation, and no entry-point discovery. Anything beyond loading
local directories by convention is a follow-up, not part of this milestone.

## 2. Technology and build configuration

- Python **>=3.13**, pinned in `.python-version` (`3.13`).
- Runtime dependencies: **`textual`** and **`pydantic`**.
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
src/toon/ui/content.py       # host content area / view manager      (M1/M3)
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
  - `open_screen(name: str) -> None`
  - `show_widget(name: str) -> None`
  - `clear_output() -> None` (used by the built-in `clear` command)
  - `reset_views() -> None` (used by the built-in `reset` command; pops plugin
    screens and unmounts widget contributions)
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
    self, name: str, factory: WidgetFactory, *, description: str = ""
) -> None: ...
```

Duplicate or invalid names raise `RegistrationError`.

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
  (`open_screen` / `show_widget`) — this is the **only navigation mechanism**;
  do not add a second one.
- Layout/navigation arrangement: the base screen holds a **persistent content
  area above the REPL**, so widget contributions mount into the content area
  while the REPL stays usable. Screen contributions are **pushed onto the
  Textual screen stack** and **`Escape` pops back** to the REPL. The REPL lives
  on the base screen and is **never destroyed**.
- The base screen is framed by two **host-owned, plugin-free** bars: a header
  (`toon/ui/header.py`) with the title and a live clock, and a footer
  (`toon/ui/footer.py`) listing every visible key binding plus the
  command-palette hint. Add a shortcut simply by adding a `Binding(...,
  show=True)` to `ToonApp.BINDINGS`; add extra segments/hints via
  `AppHeader.build_segments` and `AppFooter.EXTRA_HINTS`.

### Command-to-view mechanism (worked example)

The mechanism is: a command handler calls `ctx.host` — nothing else. There is no
second navigation path, and the host never special-cases a plugin name.

```python
# plugins/ui_demo/plugin.py (reference UI extension, M3)
def register(registry: ExtensionRegistry) -> None:
    registry.register_widget("demo_widget", make_demo_widget, description="...")
    registry.register_screen("demo_screen", make_demo_screen, description="...")
    registry.register_command(Command("demo_widget", demo_widget, "Show the widget."))
    registry.register_command(Command("demo_screen", demo_screen, "Open the screen."))


def demo_widget(ctx: CommandContext) -> str:
    ctx.host.show_widget("demo_widget")   # -> mounted in the content area
    return "Showing the 'demo_widget' widget in the content area."


def demo_screen(ctx: CommandContext) -> str:
    ctx.host.open_screen("demo_screen")   # -> pushed; Escape returns to the REPL
    return "Opened the 'demo_screen' view. Press Escape to return to the REPL."
```

- `show_widget(name)` calls the registered factory for a **fresh** widget and
  mounts it in the host content area (replacing any current content).
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
