# 0076. VM Expressiveness (Phase 1 exit criteria)

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Grill-Me Resolution #26 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **VM Expressiveness (Phase 1 exit criteria)**.

## Decision
Seven systems run on the same unmodified engine core, each with golden scenarios: d20 roll-over; d100 roll-under with degrees; 2d6 tiers + clocks; dice-pool-with-successes; step-dice or symbol-dice; bidding/resource-wager or card-draw (Fate Deck / momentum style); and a rules-light "no-stat" narrative fixture. Any engine-core change required is a design bug: extend the building-block vocabulary rather than special-casing.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
