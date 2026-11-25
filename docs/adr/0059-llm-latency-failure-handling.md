# 0059. LLM Latency & Failure Handling

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Design Resolution #9 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **LLM Latency & Failure Handling**.

## Decision
Non-blocking by design. Deterministic engine and MUD commands always respond instantly. Slow LLM calls stream tokens with a visible "GM is thinking" indicator and a configurable timeout (e.g. 60s). On timeout/failure the system offers Retry, Switch to Fallback Provider, or Continue with a deterministic stub. In multiplayer, other players' deterministic actions are never blocked by a pending LLM call.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
