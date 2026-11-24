# 0056. Agnosticism Enforcement

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Grill-Me Resolution #6 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Agnosticism Enforcement**.

## Decision
A golden-file conformance suite (scripted scenarios, seeded RNG, expected event logs per showcase ruleset), a CI lint that fails on any game-term reference (HP, AC, d20, etc.) in engine-core code, and a 4th deliberately unusual fixture ruleset added in Phase 1 to expose hidden assumptions.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
