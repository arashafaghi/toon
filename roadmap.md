# Toon: Fixture-First Monitoring UI Plan

## Goal

Build a useful Textual monitoring UI that can run with fake data at home and real internal data at work, without changing the UI code.

Keep the implementation simple. Do not build a general-purpose framework.

## Phase 1 — Define the data contract

1. Inspect the existing code before making changes, especially:
   - `ToonApp` and application startup
   - Plugin loading and registration
   - How views receive dependencies
   - Existing demo plugins and UI components

2. Add a small set of plain data models for the first monitoring feature. Start with Jenkins jobs and builds only.

3. Define a minimal `JenkinsProvider` protocol with the operations the UI actually needs, for example:
   - List jobs
   - Retrieve a specific build and its status

4. Use the project's existing conventions and dependencies where practical. Do not introduce new frameworks unnecessarily.

**Deliverable:** A small, clear contract between the UI and its data source.

## Phase 2 — Implement fixture data

1. Implement a `FixtureJenkinsProvider` that returns instances of the new models.
2. Include a small, realistic set of fixture data:
   - Successful builds
   - Failed builds
   - Running builds
   - Jobs with no builds
   - Empty job lists
   - Provider errors or unavailable data
3. Keep fixtures committed to the public repository. Use invented data, not real internal data.
4. Make fixture-provider selection straightforward for local development.

**Deliverable:** The UI can obtain all its data without connecting to Jenkins or any internal service.

## Phase 3 — Build one useful monitoring screen

1. Implement one Jenkins monitoring view using the provider interface.
2. Show a list of jobs and their latest build status.
3. Allow the user to select a job and inspect its build details.
4. Handle loading, empty results and provider errors clearly.
5. Follow the existing Toon architecture and Textual conventions. Reuse existing components where appropriate.
6. Keep all data retrieval behind the provider interface. Do not add mock-specific conditionals to the UI.

**Deliverable:** A functional monitoring screen that works with fixture data.

## Phase 4 — Prepare for the work integration

1. Make provider selection configurable without changing the UI.
2. Keep the public repository free of internal endpoints, credential-handling code and proprietary dependencies.
3. Document the minimal interface that a real Jenkins provider must implement.
4. Keep the real provider outside the public repository, in a private repository or work-only directory.
5. At work, implement the real provider using the approved internal credential retrieval and Jenkins libraries. Map their results into the same public data models.

Start with read-only access.

**Deliverable:** A clear, documented integration point that can be implemented at work without rewriting the UI.

## Constraints

- No AI integration.
- No sidecar service or HTTP API for now.
- No test suite or snapshot testing in this scope.
- No multi-provider framework or speculative abstractions.
- No broad refactoring of the existing application.
- No changes to the UI based on whether fixture or real data is selected.
- Do not implement later phases prematurely.

## Working rules

- Inspect the current implementation before editing.
- Make the smallest changes that fit the existing architecture.
- Complete each phase before moving to the next.
- Report the files changed and summarize the implementation after each phase.
- If the existing architecture prevents a clean implementation, explain the specific problem and propose the smallest correction before expanding scope.

Begin with Phase 1. Do not implement all phases at once.