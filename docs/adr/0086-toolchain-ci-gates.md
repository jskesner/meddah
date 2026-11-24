# 0086. Toolchain & CI Gates

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Grill-Me Resolution #36 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Toolchain & CI Gates**.

## Decision
Python 3.12+, `uv` (lockfile), `ruff`, `pyright` (strict on `ruleset_vm`, standard elsewhere), `pytest` + Hypothesis. TypeScript strict, pnpm, ESLint, Prettier, Vitest, Playwright. Pre-commit runs fast checks. Required CI gates: lint, type-check, unit tests, import-linter, agnosticism lint, schema-staleness check, perf-budget tests. No scheduled nightly jobs (hobby scope); slower jobs run on demand or at release.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
