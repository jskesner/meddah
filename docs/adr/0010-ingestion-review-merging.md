# 0010. Ingestion Review & Merging

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Architectural Decision #10 (`docs/design/system_design_specification.md`)

## Context & Problem Statement
Architectural design constraint and domain resolution for **Ingestion Review & Merging** in Meddah: The Universal Story Engine.

## Decision
**Interactive Staging & Diff Review Workbench**: Extracted rules display confidence scores, side-by-side source citations (page/section), and a visual conflict resolver (`Add`, `Merge`, `Override`, `Skip`) before committing.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Enforced by phase DoD suites (`pytest -m zero_ai`, `tools/lint_agnosticism.py`, `tools/lint_modularity.py`, and `import-linter`) as implementation lands.
