# 0055. Playable Test Criterion

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Design Resolution #5 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Playable Test Criterion**.

## Decision
Phase 2.5 is deterministic-only (no AI GM yet; the AI GM arrives in Phase 4). The first AI GM acceptance test is one scripted scenario on the d20 fantasy showcase ruleset: a 30-minute session with no rules errors, no hallucinated mechanics, and every roll resolved by the VM.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
