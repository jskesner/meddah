# 0092. Spikes (on-failure only)

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Design Resolution #42 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Spikes (on-failure only)**.

## Decision
Decision: NO planned up-front spikes. Risky areas (PDF extraction quality, PixiJS multi-scale canvas performance, sidecar packaging, tunnel approach, local-model structured-output reliability) are tackled directly in their phases; a time-boxed spike with a written go/no-go ADR is run only if an implementation attempt fails or misses its budget. Spike code lives outside `backend/` and `desktop/`.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
