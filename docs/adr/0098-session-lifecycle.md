# 0098. Session Lifecycle

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Grill-Me Resolution #48 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Session Lifecycle**.

## Decision
`Setup → Active → Wrapping Up → Ended` (plus `Interrupted` after a crash). The host/GM can end a session manually at any time. The pacing director may only SUGGEST ending (a non-blocking "good stopping point?" prompt at a scene boundary, a configurable soft time limit, or after a cliffhanger) and never ends a session itself; solo players get the same suggestion. "Wrapping Up" finishes the current scene, takes a final checkpoint, and awards XP/milestones before the end-of-session pipeline runs. A host-configurable idle timeout prompts before auto-ending. After a crash, the next launch offers to resume or end the interrupted session.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
