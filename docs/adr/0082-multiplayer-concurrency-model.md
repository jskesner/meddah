# 0082. Multiplayer Concurrency Model

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Design Resolution #32 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Multiplayer Concurrency Model**.

## Decision
One serialized command queue per scene (actor lock), with the event log as sole source of truth. Different scenes (split parties) run in parallel; within a scene, actions process in arrival order. Reaction windows are sub-states of the pending action, and timeouts auto-resolve per the ruleset or host setting. Real-time/freeform mode batches near-simultaneous intents within a short window (~150ms) and orders them deterministically. LLM calls are async and never hold the scene lock: they propose tool calls that re-enter the queue and are re-validated against current state; stale proposals are rejected and the GM re-plans.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
