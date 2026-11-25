# 0083. Repository Layout & Module Boundaries

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Design Resolution #33 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Repository Layout & Module Boundaries**.

## Decision
Monorepo: `backend/` (Python, src layout, `uv` workspace), `desktop/` (TypeScript, pnpm), `sample_rulesets/`, `schemas/` (generated JSON Schemas), `docs/` (incl. `docs/adr/`), `tools/`. Strict one-way backend dependency order enforced by import-linter in CI: `ruleset_vm` depends on nothing in the app; `storage`, `world_gen`, `systems`, `ingestion` depend on `ruleset_vm`; `agents` depends on those; `multiplayer` and `media` sit above; the API layer is on top. TypeScript wire types and JSON Schemas are generated from the Pydantic models by one script; CI fails if generated files are stale.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
