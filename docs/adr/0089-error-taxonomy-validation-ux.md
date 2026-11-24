# 0089. Error Taxonomy & Validation UX

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Grill-Me Resolution #39 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Error Taxonomy & Validation UX**.

## Decision
(1) Author errors (ruleset/world/package) carry a stable code, file/block path, line/column where available, plain-language message, and suggested fix; shown in the Studio problems panel and CLI. (2) User-facing runtime errors are friendly, localized by string ID, never show stack traces. (3) Engine bugs (invariant violations) are caught at the scene-queue boundary, logged with a correlation ID, roll the scene back to the last consistent event, and offer "Export Diagnostics". Stable codes (`RPG-E####`) documented in `docs/errors.md`. `meddah validate <package>` CLI runs the same validator as the app.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
