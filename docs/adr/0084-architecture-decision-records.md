# 0084. Architecture Decision Records

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Design Resolution #34 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Architecture Decision Records**.

## Decision
Decisions become lightweight ADRs in `docs/adr/` (`NNNN-title.md`: context, decision, consequences, status). The 46 decisions plus Section 2.1 seed the initial set; the two spec files remain the narrative overview. Changing a decision means a new superseding ADR, never a silent edit. Phase Definition of Done includes "ADRs updated".

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
