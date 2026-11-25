# 0061. Versioning & Save Compatibility

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Design Resolution #11 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Versioning & Save Compatibility**.

## Decision
Every `.rpgrules`/world/campaign file carries a `schema_version` and content hash. A campaign pins the exact ruleset version it started on; ruleset edits create a new version and the user chooses "Stay on pinned" or "Migrate" (with a diff and an automatic checkpoint first). Engine upgrades ship event-log migration scripts, so old saves open, or fail with a clear message, never silently corrupt.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
