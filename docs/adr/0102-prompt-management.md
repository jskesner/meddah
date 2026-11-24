# 0102. Prompt Management

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Grill-Me Resolution #52 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Prompt Management**.

## Decision
Prompts are versioned template files under `backend/app/agents/prompts/` (one per task), each with front-matter: `id`, `version`, typed variables schema, token-budget section weights, required output schema, and optional per-model-family overrides. CI fails on missing variables or budget overflow. Prompt hash/version are recorded in AI event provenance. Users can override any prompt via a user prompts folder, shown in a Prompt Library panel with diff against the default and a reset button. Eval suites run against a pinned prompt version, and a prompt change requires an eval result note in the PR.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
