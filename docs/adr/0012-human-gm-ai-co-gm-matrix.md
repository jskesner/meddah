# 0012. Human GM + AI Co-GM Matrix

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Architectural Decision #12 (`docs/design/system_design_specification.md`)

## Context & Problem Statement
Architectural design constraint and domain resolution for **Human GM + AI Co-GM Matrix** in Meddah: The Universal Story Engine.

## Decision
**5-Domain Per-Subsystem Assistance Matrix**: Human GMs independently set AI autonomy (`Off`, `Suggest in Whisper`, `Auto-Execute`) across: *(1) Scene Descriptions, (2) NPC Dialogue/RP, (3) Combat Turn Execution, (4) Rules/Compendium Oracle, and (5) World/Encounter Generation*.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Enforced by phase DoD suites (`pytest -m zero_ai`, `tools/lint_agnosticism.py`, `tools/lint_modularity.py`, and `import-linter`) as implementation lands.
