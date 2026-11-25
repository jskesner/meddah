# 0065. Campaign On-Disk Layout & Integrity

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Design Resolution #15 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Campaign On-Disk Layout & Integrity**.

## Decision
A campaign is a folder: `campaign.sqlite` (append-only event log, checkpoints, overlay projections; WAL mode), `media/` (content-addressed cache), and `pins.json` (pinned ruleset/world versions + hashes). `.rpgcampaign` export is a zip of that folder after a SQLite checkpoint/vacuum. Projections are rebuildable from the event log; import verifies by replaying events and comparing a state hash, and repairs a corrupt projection instead of failing.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
