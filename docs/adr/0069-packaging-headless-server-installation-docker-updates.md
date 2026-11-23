# 0069. Packaging, Headless Server Installation, Docker & Updates

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Grill-Me Resolution #19 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Packaging, Headless Server Installation, Docker & Updates**.

## Decision
- **Desktop App**: Linux-first, with Windows/macOS builds via CI once the MVP is stable. `electron-builder` (AppImage/deb, then NSIS/dmg) with the Python backend as a frozen sidecar.
   - **Desktop App**: Linux-first, with Windows/macOS builds via CI once the MVP is stable. `electron-builder` (AppImage/deb, then NSIS/dmg) with the Python backend as a frozen sidecar.
   - **Optional Headless / Server-Only Installation (No Desktop GUI Required)**: The Python backend (`backend/`) can be installed standalone via `uv tool install ./backend` / `pipx` / `pip` (zero Electron or Node.js runtime needed), managed via the `meddah` CLI (`meddah serve`, `meddah campaign`, `meddah seat`, `meddah backup`, `meddah ruleset`), and accessed via CLI MUD (`meddah attach`) or the bundled static **Browser Light Client** (`--serve-web-client`).
   - **Official Headless Server Docker Image**: Multi-stage `docker/Dockerfile.server` and `docker/docker-compose.server.yml` packaging the Python server + static Browser Light Client assets (with non-root user, `/data` volume, healthcheck, and optional `ollama` service profile).
   - LLM/TTS/image models are never bundled; updates are manual download/pull plus a version-check notice; no silent auto-update in MVP.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
