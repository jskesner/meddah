# 0072. Telemetry & Logging

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Design Resolution #22 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Telemetry & Logging**.

## Decision
No telemetry, analytics, or call-home, ever. Local structured JSONL logs (rotated, size-capped) with per-subsystem levels. A separate opt-in "AI Transcript" log (prompts/responses with provenance) is off by default because it may contain private content. "Export Diagnostics Bundle" collects redacted logs, versions, and hardware info, with a preview before saving. The only outbound traffic is user-configured providers and an optional manual version check.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
