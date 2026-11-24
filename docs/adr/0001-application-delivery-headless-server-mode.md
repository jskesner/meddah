# 0001. Application Delivery & Headless Server Mode

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Architectural Decision #1 (`docs/design/system_design_specification.md`)

## Context & Problem Statement
Architectural design constraint and domain resolution for **Application Delivery & Headless Server Mode** in Meddah: The Universal Story Engine.

## Decision
**Dual Delivery Targets**: **(A) Full Standalone Desktop App** (`Electron + React/TypeScript + PixiJS`) managing either its own embedded local Python sidecar OR connecting as a remote Host/GM Studio workstation to a Headless Server; and **(B) Optional Headless / Server-Only Installation & Official Docker Image** (`meddah serve` via `uv` / `pipx` supporting standard table mode or `--mode guild-server` multi-tenant daemon + `Dockerfile.server` + `docker-compose.server.yml` with `ollama-nvidia`, `ollama-amd` ROCm, `ollama-vulkan`, `ollama-cpu`, `piper-tts`, and `tunnel` profiles + `meddah gpu-check` host setup tool) that installs **only** the Python backend server (zero Electron/GUI dependencies), manages a multi-campaign library with 1 hot-swappable active session, and serves the unified **Browser Guest/Light Client** (`--serve-web-client`) with role-gated Host/GM administration alongside full `meddah` CLI server management.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Enforced by phase DoD suites (`pytest -m zero_ai`, `tools/lint_agnosticism.py`, `tools/lint_modularity.py`, and `import-linter`) as implementation lands.
