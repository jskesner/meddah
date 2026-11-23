# 0057. AI/VM Consistency Contract

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Grill-Me Resolution #7 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **AI/VM Consistency Contract**.

## Decision
The LLM may only propose structured tool calls (roll request, apply effect, move entity, spawn, etc.). The VM validates each against the ruleset schema and current state and commits it as an event. Invalid calls are rejected with an error and retried up to N times, then fall back to a deterministic or narrative-only response. Prose never changes state directly.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
