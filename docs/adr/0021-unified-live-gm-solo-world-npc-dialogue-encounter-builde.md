# 0021. Unified Live GM & Solo World, NPC, Dialogue & Encounter Builder Suite

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Architectural Decision #21 (`docs/design/system_design_specification.md`)

## Context & Problem Statement
Architectural design constraint and domain resolution for **Unified Live GM & Solo World, NPC, Dialogue & Encounter Builder Suite** in Meddah: The Universal Story Engine.

## Decision
**Reuse World Studio Subsystems Pre-Game & Live In-Session (`desktop/src/components/world_studio/` — Core Builder in [MVP Phase 6])**: Exposes `world_gen`, `vtt`, and `compendium` both pre-game and **live mid-session** (writing to the Campaign CoW Overlay, baking to the Base World Template, or placing Spoiler-Free Solo Seed Pins) via an integrated 100% Zero-AI Builder Suite featuring: **(1) Multi-Scale Drag-and-Drop World & Multi-Floor Dungeon Graph Canvas (`WorldAndDungeonCanvas.tsx`)** (stamp regions, hexes, settlements, POIs, and multi-floor dungeon wings; wire portals/stairs/chasms; inspect cascading `SettingOntologyBlock` and `.rpgtileset` inheritance); **(2) Settlement, District & Establishment Builder** (shops with merchant containers & `UnlockedMerchandiseRegistry` scopes, taverns, temples/clinics, guildhalls, West Marches `HubTopologyBlock` config, and urban `safety_rating` danger zoning); **(3) No-Code NPC, AI Companion & Faction Designer (`NPCAndFactionStudio.tsx`)** (clone/customize statblocks, visually configure the **Mind Sheet** [personality/obedience sliders, core moral lines, likes/dislikes, tiered dossier secrets, paper-doll portrait & outfit presets, and per-entity `EntityLootConfigBlock` / `vitality_topology` overrides], and wire Faction disposition matrices, borders, and Progress Clocks); **(4) Zero-AI (`Tier A`) Dialogue Topic-Chip, Bark & Solo Oracle Table Designer (`DialogueAndOracleStudio.tsx`)** (visually author disposition-gated NPC conversation topic chips, social contest unlocks, FTS5 keyword triggers, personality-tagged companion barks, and custom Solo Fate/Meaning/Rumor/Sensory tables); **(5) Encounter Builder, 2.5D Tactical Stage Designer & Agnostic Threat Estimator** (100% manual per-instance overrides, traps/waves, and 1-click live deployment); and **(6) Automated World & Adventure Consistency Linter (`WorldValidationLinter.tsx`)** (graph reachability checks ensuring keys aren't locked behind their own doors, portal/staircase integrity checks, pinned ruleset reference checks, and 3-Clue Matrix bottleneck verification).

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Enforced by phase DoD suites (`pytest -m zero_ai`, `tools/lint_agnosticism.py`, `tools/lint_modularity.py`, and `import-linter`) as implementation lands.
