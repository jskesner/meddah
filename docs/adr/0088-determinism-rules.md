# 0088. Determinism Rules

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Grill-Me Resolution #38 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Determinism Rules**.

## Decision
Hard rule inside `ruleset_vm` and event-apply code. (1) All randomness from named, seeded RNG streams per scene (`dice`, `loot`, `encounters`, ...); each roll's stream position is recorded in its event. (2) No wall-clock, system RNG, or unordered-set iteration there (time comes from the in-world clock/events). (3) Event application is a pure function of (state, event). (4) AI output is recorded as events and never regenerated on replay. (5) A replay-determinism test replays every golden campaign and asserts identical state hashes; a lint forbids `random`, `time.time`, and `datetime.now` in those packages.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
