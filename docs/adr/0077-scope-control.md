# 0077. Scope Control

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Grill-Me Resolution #27 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Scope Control**.

## Decision
Each phase has a Definition of Done: acceptance tests, perf budget check, agnosticism lint pass, docs, and a demo script. Post-MVP subsystems may only add building-block types and extension points, never modify MVP core schemas without a versioned migration. A subsystem starts only when its dependencies are green. A scope review at the end of each phase may cut or defer items.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
