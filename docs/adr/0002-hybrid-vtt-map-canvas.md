# 0002. Hybrid VTT Map Canvas

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Architectural Decision #2 (`docs/design/system_design_specification.md`)

## Context & Problem Statement
Architectural design constraint and domain resolution for **Hybrid VTT Map Canvas** in Meddah: The Universal Story Engine.

## Decision
**Dual-Scale Map View**: Macro **Node/Room Graph** (visual MUD rooms, exits, and backdrops) seamlessly zooming into a Micro **2D Tactical Square/Hex Grid** (tokens, measurement, walls/lighting fog-of-war).

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Enforced by phase DoD suites (`pytest -m zero_ai`, `tools/lint_agnosticism.py`, `tools/lint_modularity.py`, and `import-linter`) as implementation lands.
