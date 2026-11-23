# 0091. Documentation as a Deliverable

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Grill-Me Resolution #41 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Documentation as a Deliverable**.

## Decision
Docs are part of Definition of Done. Required: `docs/ruleset-authoring.md` (building-block reference partly generated from JSON Schemas, with annotated showcase examples), `docs/quickstart.md`, `docs/architecture.md`, `docs/errors.md`, `docs/adr/`, `CONTRIBUTING.md`. Each building-block type has a docstring-derived reference page so docs can't drift. In-app help links to the same docs; the tutorial scenario doubles as living documentation.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
