# 0067. Localization (i18n)

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Design Resolution #17 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Localization (i18n)**.

## Decision
Not in MVP, but designed in: all player-facing strings and engine messages live in ID-keyed string tables (no hardcoded English in code paths). Rulesets carry a language tag; the AI GM is told the table's preferred language; TTS voices are chosen per language; UI translation packs are a post-MVP hook.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
