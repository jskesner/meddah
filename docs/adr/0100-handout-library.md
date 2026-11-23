# 0100. Handout Library

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Grill-Me Resolution #50 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Handout Library**.

## Decision
Campaign-scoped. The host imports images (PNG/JPG/WebP/SVG), PDFs (rendered per page), and text/Markdown via drag-and-drop, file picker, or paste, or extracts them from an ingested module. Files are validated (type sniffing, size cap, decompression-bomb limits, EXIF stripped) and stored content-addressed under `media/handouts/` with metadata (title, tags, folder, GM notes, source, license note). Visibility: Hidden, Shared with all, or Shared with selected seats; the host can "Show to players" as a pop-up or pin it in a Handouts drawer. Revealed handouts persist in the player's journal. Visibility changes are replayable events and the server only sends bytes to authorized seats. Handouts can attach to rooms, NPCs, or quests to surface automatically. Handout export is NOT supported (they come from external sources).

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
