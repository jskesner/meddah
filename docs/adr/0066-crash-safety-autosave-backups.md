# 0066. Crash Safety, Autosave & Backups

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Design Resolution #16 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Crash Safety, Autosave & Backups**.

## Decision
Every event commits to SQLite (WAL, fsync on commit) before being acknowledged, so a crash loses at most the in-flight action. Automatic checkpoints on scene change, rest, and every N minutes. Rolling backups of the campaign folder (default last 5, on session start/end) go to a separate configurable location. After an unclean shutdown the app offers Resume (replay from last checkpoint) or Restore from backup. Multiplayer guests reconnect by re-syncing from the host's state.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
