# 0054. MVP Boundary & Contiguous Phase Ordering

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Design Resolution #4 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **MVP Boundary & Contiguous Phase Ordering**.

## Decision
All MVP phases come numerically first (**Phases 1–6 plus the Phase 2.5 thin playable slice**): Phase 1 (Core Ruleset VM, Module Registry & MUD Parser), Phase 2 (Ruleset Ingestion & 14 Probes), Phase 2.5 (Terminal CLI MUD & Headless Server Slice), Phase 3 (Event-Sourced Persistence, Cosmology, Multi-Floor Dungeons & Chronology), Phase 4 (Deterministic & AI GM Director, Difficulty/Mercy & Quests), Phase 5 (Host-Authoritative Multiplayer, Split-Party, Safety & Media), and Phase 6 (Desktop Shell, Unified Browser Web Client, MUD Terminal, Core 2.5D VTT Canvas, Dynamic Character Sheet, 3-Mode Builder, 4-Tab Capabilities Deck & **Visual Ruleset Studio GUI**). All Post-MVP modular expansions follow in well-balanced contiguous order (**Phases 7–14**).

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
