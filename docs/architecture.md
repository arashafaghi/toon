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
  Built-in **`help`**, **`clear`**, and **`plugins`** commands are registered by
  the host at startup.
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
