# 0103. Cloud Usage Ledger

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Design Resolution #53 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Cloud Usage Ledger**.

## Decision
Each provider call records provider, model, task id, prompt/completion/cached tokens, latency, and an estimated cost from a user-editable price table (per 1M tokens; per image; per 1k TTS characters) shipped with defaults and a "prices may be stale" note. Local providers record tokens/time with cost 0. The ledger lives in the campaign database SEPARATE from the game event stream (so it never affects replay or determinism). A Usage panel aggregates by session, campaign, provider, and task. Provider-reported counts are preferred, with a local tokenizer estimate as fallback.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
