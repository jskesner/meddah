# 0094. Manual Roll / Sheet-Override Play Modes

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Grill-Me Resolution #44 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Manual Roll / Sheet-Override Play Modes**.

## Decision
There is NO formal manual dice-entry feature in the engine. Instead, solo players and GMs/hosts may (a) set the engine to NOT resolve player-facing rolls (background RNG for world systems may still run), and (b) grant players permission to directly edit their character sheets and status (HP, mana, etc.), effectively bypassing the deterministic rules. Direct edits are committed as audited `SHEET_OVERRIDE` events so replay and timeline rewind stay consistent.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
