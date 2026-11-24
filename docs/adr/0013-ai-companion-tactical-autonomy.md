# 0013. AI Companion Tactical Autonomy

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Architectural Decision #13 (`docs/design/system_design_specification.md`)

## Context & Problem Statement
Architectural design constraint and domain resolution for **AI Companion Tactical Autonomy** in Meddah: The Universal Story Engine.

## Decision
**Hybrid Tactical + Persona AI with Dynamic Obedience**: Companions act autonomously using deterministic tactical heuristics + persona flair, follow player orders when Trust/Respect supports it, and can balk/improvise if an order violates core beliefs (with a Host override toggle for direct player combat control).

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Enforced by phase DoD suites (`pytest -m zero_ai`, `tools/lint_agnosticism.py`, `tools/lint_modularity.py`, and `import-linter`) as implementation lands.
