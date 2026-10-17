# Roadmap: Minimal Textual Plugin Runner

## Goal

Build a small Python terminal application that proves one architectural idea:

> A host application discovers local extensions, lets them register commands and UI contributions, and connects those contributions to an interactive REPL and the main Textual interface.

This is an architecture proof, not a general-purpose plugin framework.

## Non-goals

Do **not** implement these in the first version:

- Runtime plugin installation, hot reload, or unloading
- Third-party package distribution or Python entry-point discovery
- Process isolation or a security sandbox
- A sophisticated command language, shell compatibility, pipes, or scripting
- Persistent sessions, configuration frameworks, databases, or telemetry
- A large event bus, dependency-injection framework, or elaborate lifecycle system

Extensions are trusted Python code executed in-process. Document this limitation.

## Technology and constraints

- Python 3.11+ (use the version already selected by the repository if one exists and it is supported).
- Textual for the TUI.
- `asyncio` through Textual's supported mechanisms; do not create a second event loop.
- `pytest` and Textual's testing utilities for automated tests.
- pydantic for validation
- Use the repository's existing package/build conventions where practical. If none exist, use a minimal `pyproject.toml`.
- Keep the runtime/extension API independent of Textual where practical. Textual-specific UI types belong at the UI boundary.

## Minimum successful demonstration

On startup, the host scans `plugins/` and loads valid extensions. It shows a usable TUI with an interactive REPL.

The demonstration must include:

1. A built-in `help` command and a `plugins` command.
2. One example extension that registers a command returning text.
3. One example extension that registers a command and a Textual widget or screen.
4. Invoking a command from the REPL dispatches it and displays its result without restarting the application.
5. Invoking the UI extension's command opens its screen, or selects its registered widget in the host's designated content area.
6. A plugin registration or import failure is reported clearly and does not prevent other valid plugins or the host from starting.
7. Automated tests cover registry/dispatch behavior and the essential UI flow.

The extension examples must use the public extension API. They must not edit or import private host implementation details.

## Minimal architecture

Keep the number of concepts deliberately small.

- **Host/App:** creates the Textual application and owns startup/shutdown.
- **Plugin loader:** scans the local `plugins/` directory, imports plugins, and invokes their registration entry point.
- **Registry:** stores registered commands and UI contributions; validates names and rejects duplicates clearly.
- **Command dispatcher:** resolves a command name, passes parsed arguments, awaits execution when needed, and returns a result or a controlled error.
- **REPL widget:** accepts input, shows command history/output, and dispatches commands. It must remain usable while an extension view is open.
- **View/content manager:** connects registered screens/widgets to the host UI. Extensions contribute UI; the host retains control of the application lifecycle and overall layout.
- **Extension API:** the small, documented contract used by plugins to register capabilities.

Do not add an event bus unless a demonstrated requirement cannot be met with direct calls or Textual messages.

## Proposed repository layout

Adapt to an existing repository rather than reorganizing it unnecessarily.

```text
.
├── pyproject.toml
├── README.md
├── roadmap.md
├── src/
│   └── tui_runner/
│       ├── __init__.py
│       ├── app.py
│       ├── runtime/
│       │   ├── registry.py
│       │   ├── dispatcher.py
│       │   └── plugin_loader.py
│       ├── api/
│       │   └── extension.py
│       └── ui/
│           ├── repl.py
│           └── content.py
├── plugins/
│   ├── hello/
│   │   └── plugin.py
│   └── system_info/
│       └── plugin.py
└── tests/
    ├── test_registry.py
    ├── test_dispatcher.py
    ├── test_plugin_loader.py
    └── test_app.py
```

This is a guide, not a requirement to create a file for every concept. Prefer fewer modules if that keeps the implementation clearer.

## Stable contracts to agree before parallel implementation

The integrator must define and commit the first version of these contracts before delegated implementation begins. Keep them minimal and type-annotated.

### Plugin entry point

Each immediate child directory of `plugins/` is one plugin candidate. For the first version, each candidate contains `plugin.py` exposing:

```python
def register(registry: ExtensionRegistry) -> None:
    ...
```

The loader imports each candidate and calls `register`. Do not recursively scan arbitrary Python files. Ignore directories that are clearly not plugin packages according to one documented rule (for example, directories without `plugin.py`).

Plugin names should come from a simple explicit metadata field or the directory name; choose one rule and document it. Do not build a manifest system.

### Registry

The registry should support the minimum operations:

```python
register_command(command)
register_screen(name, factory, *, description="")
register_widget(name, factory, *, description="")
```

Use concrete Protocols or small typed data classes for registered items. Final names/signatures are owned by the integrator and must be written into the public API before agents implement against them.

- Commands have a unique name, description, and callable handler.
- Screen/widget registrations have a unique name and a factory that creates the corresponding UI contribution.
- Factories should create a fresh UI instance when opened/mounted; do not reuse an already-mounted Textual widget.
- Duplicate names produce a clear registration error.
- The REPL and host should not need special-case logic for individual plugin names.

### Command execution

- Commands may be synchronous or asynchronous, but choose one clear handler convention and normalize it in the dispatcher. Prefer async handlers if this simplifies Textual integration.
- Start with simple tokenization via `shlex.split`; no shell expansion, pipes, or command chaining.
- Empty input does nothing.
- Unknown commands and invalid input return readable errors without crashing the app.
- `help` is generated from registered commands rather than maintained as a separate list.
- Commands return a small, documented result type (or a deliberately simple string result for the first milestone). Do not let plugins directly write into the REPL widget.
- A command can request a registered screen/widget through a documented host-facing context or a dedicated built-in command. Choose one mechanism; do not implement multiple competing navigation paths.

### UI contributions

- The host owns the overall Textual `App`, its layout, and REPL lifetime.
- A screen contribution is a factory for a Textual `Screen` (or an equivalent documented navigation unit).
- A widget contribution is a factory for a Textual `Widget` mounted in a designated host content area.
- The initial demo must prove at least one screen **and** one widget contribution can be registered and used. A single example may register both.
- The REPL must remain accessible after navigating to a contributed screen. Decide the smallest Textual layout/navigation arrangement that achieves this and document it.
- Keep Textual-specific types in the UI-facing part of the API; do not make the core registry depend on rendering details beyond the minimum needed to store factories.

### Failure handling

- Catch errors per plugin during import/registration; report plugin name and useful exception context.
- One bad plugin must not block later plugins from loading.
- Catch command execution errors at the dispatcher/REPL boundary and display them without terminating the application.
- Do not silently swallow exceptions. Keep diagnostics concise and useful.

## Milestones and acceptance criteria

### M0 — Inspect and agree interfaces

Tasks:
- Inspect the repository and existing conventions.
- Record the agreed public interfaces and folder layout in a short `docs/architecture.md` or in this roadmap.
- Create the minimal project/test setup if needed.

Acceptance:
- Dependencies and supported Python version are explicit.
- Plugin entry point, registry methods, command handler convention, UI factory convention, and REPL navigation behavior are decided.
- No production framework is introduced without a concrete need.

### M1 — Host shell and interactive REPL

Tasks:
- Create the Textual app and basic layout.
- Implement the REPL input/output/history.
- Implement a small command registry and dispatcher.
- Add `help`, `clear` (if straightforward), and `plugins` commands.

Acceptance:
- The app launches with one documented command.
- The user can enter several commands in sequence without restarting.
- `help` lists registered commands.
- Empty input, unknown commands, and handler exceptions are handled safely.
- Unit tests cover command registration and dispatch.

### M2 — Local plugin loading

Tasks:
- Implement startup discovery of `plugins/*/plugin.py`.
- Load each plugin and call its documented `register(registry)` entry point.
- Add a text-only example plugin.
- Report loaded plugins and per-plugin failures.

Acceptance:
- Adding the example plugin directory makes its command available on startup without editing host code.
- `plugins` reports successfully loaded plugins and failures.
- A malformed plugin does not prevent a valid plugin from loading.
- Tests cover discovery, successful registration, duplicate names, and isolated load failures.

### M3 — UI contributions

Tasks:
- Add screen and widget factory registration.
- Implement the host's content/view manager.
- Add an example UI plugin that registers a command and contributes both a screen and a widget.
- Choose a simple command-to-view mechanism and document it.

Acceptance:
- The plugin command can open its registered screen or activate its widget.
- The widget is mounted in the host's designated content area.
- The REPL remains usable and can be reached after opening a screen.
- Fresh widget/screen instances are created when required by Textual.
- UI integration tests verify the essential path.

### M4 — End-to-end proof and documentation

Tasks:
- Exercise the application using only the public extension API.
- Add a short README with setup, run, test, extension authoring, and limitations.
- Run formatting, linting, and all tests using the repository's chosen tools.
- Fix integration defects; do not add new features.

Acceptance:
- A new developer can install dependencies, run the app, invoke built-in and plugin commands, open plugin UI, and run tests by following the README.
- The end-to-end demonstration works from a clean checkout.
- No example plugin imports host internals or requires host source changes.
- All automated tests pass.

## Agent delegation plan

Use one orchestrator/integrator as the **sole owner of architecture, public interfaces, and final integration**. Delegate implementation only after the relevant contracts are written down.

### Integrator (main agent) — owns all milestones

Responsibilities:
- Inspect the repository and establish conventions.
- Define and commit public types/signatures before delegation.
- Own `roadmap.md`, architecture decisions, dependency choices, and cross-module integration.
- Assign disjoint files and explicit inputs/outputs to agents.
- Review all changes against acceptance criteria.
- Run the full test suite and end-to-end demonstration.
- Resolve conflicts; only the integrator changes shared contracts.

### Agent A — registry and dispatcher

Owns:
- `runtime/registry.py`
- `runtime/dispatcher.py`
- Corresponding unit tests

Must not:
- Change the public contract after it is agreed.
- Implement Textual UI or plugin discovery.
- Modify shared app files.

Deliverable:
- Registry and dispatcher satisfying the agreed API, with focused tests.

### Agent B — plugin loader and example plugins

Owns:
- `runtime/plugin_loader.py`
- Example plugin files under `plugins/`
- Plugin-loader tests

Must not:
- Change registry/API signatures.
- Import private app/UI implementation details.
- Modify the REPL or main app.

Dependency:
- Starts only after the extension entry point and registry API are fixed.

Deliverable:
- Loader plus examples using only the public extension API.

### Agent C — REPL and UI contribution host

Owns:
- `ui/repl.py`
- `ui/content.py`
- UI-focused tests, in coordination with the integrator

Must not:
- Redesign the registry or plugin loader.
- Create a separate event loop.
- Hard-code example plugin names.

Dependency:
- Starts after the command result and UI contribution contracts are fixed.

Deliverable:
- Interactive REPL and generic UI host that consume registry/dispatcher APIs.

### Parallelism rules

- M0 and interface design are sequential; do not delegate competing architecture designs.
- Agents A, B, and C can work in parallel only after the shared contracts are stable. If interfaces are not yet fixed, have them review designs or write tests against the agreed contract instead of independently inventing APIs.
- Assign file ownership explicitly. Avoid having multiple agents edit `app.py`, the public API module, `pyproject.toml`, or the same tests.
- The integrator owns `app.py`, dependency/build configuration, public API definitions, README, and final integration.
- Merge in small increments. Run focused tests after each merge and the full suite at M4.
- If an agent discovers an interface flaw, it must report the proposed change and impact; it must not silently change the contract.

## Quality bar

- Type annotations on public APIs.
- Clear error messages; no broad silent exception swallowing.
- No unnecessary abstraction layers.
- No global mutable plugin state beyond the host-owned registry.
- Deterministic plugin discovery order (for example, sorted directory names).
- Tests should exercise behavior, not merely implementation details.
- UI tests should use Textual's testing support where practical; keep most registry/dispatcher tests independent of Textual.
- Keep the initial implementation small enough that a developer can understand the whole architecture in one sitting.

## Definition of done

The project is done when I can:

1. Start the TUI.
2. Type `help` and see built-in and plugin commands.
3. Type a command from a plugin and see its result.
4. Type a command that opens an extension-provided screen.
5. Use an extension-provided widget in the host content area.
6. Continue using the REPL without restarting the application.
7. Add a new plugin under `plugins/` without modifying host code.
8. Run the tests and see the core architecture verified.

Anything beyond these points is a follow-up, not part of this milestone.
