# 0051. Early Thin Vertical Slice ("Phase 2.5" — Terminal CLI MUD & Headless Server Daemon)

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Design Resolution #1 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Early Thin Vertical Slice ("Phase 2.5" — Terminal CLI MUD & Headless Server Daemon)**.

## Decision
After Phases 1–2, build the interactive **Terminal CLI MUD Client (`meddah attach`)** and **Headless Server CLI (`meddah serve`)** so the 3 showcase rulesets, ingestion, and (later) the AI GM can be played, tested, and hosted from the terminal well before Phase 6. There is **no** separate "text-only browser" client—the single **Unified Browser Web Client** (which serves Spectators, Players, Co-GMs, and Headless Server Admins from one shared React web bundle) and the Electron Desktop App are built in Phase 6 [MVP] (with post-MVP studios and audiovisual spectacle in Phase 13).

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
