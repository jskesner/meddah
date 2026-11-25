# 0060. AI Content Provenance & Governance

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Design Resolution #10 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **AI Content Provenance & Governance**.

## Decision
All AI-generated content (NPCs, rooms, items, quests, ingested blocks) is committed as an event tagged with provenance (model, prompt hash, timestamp) and lives in the Campaign Overlay, never touching the immutable base ruleset or world template. Ruleset-level content is always staged in the Diff Workbench. Players can inspect, edit, lock, or discard AI content; "Bake to Template" is always an explicit user action.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
