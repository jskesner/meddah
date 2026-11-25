# 0063. Export / Import Workflow

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Design Resolution #13 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Export / Import Workflow**.

## Decision
Three portable, versioned, zip-based packages: `.rpgrules` (ruleset plus compendium), `.rpgworld` (world template with maps/tilesets, optionally bundled rules), and `.rpgcampaign` (event log, overlay, pinned ruleset, optional media). Every export shows a manifest with checksum and `schema_version`. Import runs through the Staging/Diff Workbench with conflict resolution. API keys/secrets are never included; a "player-safe" mode strips GM-only data; "Redact copyrighted compendium text" is on by default for ruleset exports. Implementation: backend in Phase 3 (storage) with Visual Ruleset & Package Studio UI in Phase 6 [MVP]; `.rpgcampaign` export/import is part of the MVP.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
