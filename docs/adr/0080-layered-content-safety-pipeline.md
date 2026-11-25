# 0080. Layered Content-Safety Pipeline

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Design Resolution #30 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Layered Content-Safety Pipeline**.

## Decision
(1) Lines/Veils and content rating are injected into every system prompt. (2) A fast deterministic keyword/pattern filter plus an optional lightweight classifier checks output before display; on a hit, regenerate once, then replace with a fade-to-black veil. (3) Provider refusals are caught, retried with a rephrased scene prompt, then fall back to a neutral narrative stub, never an error dump. (4) The X-Card always works instantly and rewinds the last beat. (5) Image and TTS prompts share the same filter. Filter hits are logged locally only.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
