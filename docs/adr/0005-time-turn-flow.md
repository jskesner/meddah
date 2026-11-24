# 0005. Time & Turn Flow

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Architectural Decision #5 (`docs/design/system_design_specification.md`)

## Context & Problem Statement
Architectural design constraint and domain resolution for **Time & Turn Flow** in Meddah: The Universal Story Engine.

## Decision
**Pluggable Flow Modes** defined by the ruleset: *Freeform/Real-Time* (Exploration), *Structured Turn-Order* (Initiative/Rounds), and *Popcorn/Phase-Based* (Narrative/PbtA/FitD), with automatic or GM-triggered transitions.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Enforced by phase DoD suites (`pytest -m zero_ai`, `tools/lint_agnosticism.py`, `tools/lint_modularity.py`, and `import-linter`) as implementation lands.
