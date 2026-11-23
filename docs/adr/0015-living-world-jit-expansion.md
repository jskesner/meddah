# 0015. Living World & JIT Expansion

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Architectural Decision #15 (`docs/design/system_design_specification.md`)

## Context & Problem Statement
Architectural design constraint and domain resolution for **Living World & JIT Expansion** in Meddah: The Universal Story Engine.

## Decision
**Faction Clocks + Lazy/JIT Expansion**: World threats/factions advance via Progress Clocks on rest/downtime ticks; stub regions/settlements expand On-Demand (JIT) when visited, stored in the Campaign Overlay with a "Bake to World Template" promotion tool.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Enforced by phase DoD suites (`pytest -m zero_ai`, `tools/lint_agnosticism.py`, `tools/lint_modularity.py`, and `import-linter`) as implementation lands.
