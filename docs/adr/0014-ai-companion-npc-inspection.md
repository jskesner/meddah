# 0014. AI Companion & NPC Inspection

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Architectural Decision #14 (`docs/design/system_design_specification.md`)

## Context & Problem Statement
Architectural design constraint and domain resolution for **AI Companion & NPC Inspection** in Meddah: The Universal Story Engine.

## Decision
**Tiered Dossier Transparency**: Players view an immersive Character Dossier showing surface traits, observed quirks, qualitative disposition ("Guarded Ally"), and unlocked backstory memories as Trust grows; Host/GM can toggle full numeric values and raw memory logs.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Enforced by phase DoD suites (`pytest -m zero_ai`, `tools/lint_agnosticism.py`, `tools/lint_modularity.py`, and `import-linter`) as implementation lands.
