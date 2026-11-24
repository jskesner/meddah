# 0104. Cost Controls

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Grill-Me Resolution #54 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Cost Controls**.

## Decision
Optional per-session, per-campaign, and per-day budget caps per provider category (LLM, image, TTS). At 80% a non-blocking warning appears. At 100% a user policy applies: "Warn and continue" (default), "Pause cloud calls and fall back to local/deterministic tier", or "Ask me each time". Pre-call estimates with a confirm step above a threshold for expensive calls (image generation, large PDF ingestion). The host's budget governs multiplayer spend; guests never use the host's keys directly because all calls go through the host backend. Everything stays local.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
