# 0123. Zero-AI Authoring Studios in MVP — Visual Compendium Catalog Manager, World/Dungeon/NPC/Faction Builder, World Consistency Linter & Dialogue/Oracle Designer (`CompendiumCatalogStudio.tsx`, `world_studio/` & `DialogueAndOracleStudio.tsx` — Phase 6 [MVP], Vol 1 §1.2.5.G, Vol 2 §1.3.5, Vol 3 §1.11, Vol 4 §1.18.5)

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Design Resolution #73 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Zero-AI Authoring Studios in MVP — Visual Compendium Catalog Manager, World/Dungeon/NPC/Faction Builder, World Consistency Linter & Dialogue/Oracle Designer (`CompendiumCatalogStudio.tsx`, `world_studio/` & `DialogueAndOracleStudio.tsx` — Phase 6 [MVP], Vol 1 §1.2.5.G, Vol 2 §1.3.5, Vol 3 §1.11, Vol 4 §1.18.5)**.

## Decision
- **Visual Compendium, Item/Apparel, Capability & Bestiary Catalog Manager (`CompendiumCatalogStudio.tsx`)**: Dual card-inspector and spreadsheet batch-editor (with CSV/Markdown-table copy-paste) for authoring items, layered clothing/cosmetics/armor (`WearableLayerSpec`), spells/maneuvers/feats/stances/reactions (`CapabilityBlock`), conditions (`ConditionVisualSpec`), rollable tables, and Bestiary monsters with a 1-click `"Clone & Variant"` builder and per-creature loot/vitality topology overrides.
   - **Visual Compendium, Item/Apparel, Capability & Bestiary Catalog Manager (`CompendiumCatalogStudio.tsx`)**: Dual card-inspector and spreadsheet batch-editor (with CSV/Markdown-table copy-paste) for authoring items, layered clothing/cosmetics/armor (`WearableLayerSpec`), spells/maneuvers/feats/stances/reactions (`CapabilityBlock`), conditions (`ConditionVisualSpec`), rollable tables, and Bestiary monsters with a 1-click `"Clone & Variant"` builder and per-creature loot/vitality topology overrides.
   - **Unified Multi-Scale World, Dungeon, NPC/Companion & Faction Studio (`WorldAndDungeonCanvas.tsx` & `NPCAndFactionStudio.tsx`)**: Delivered in Phase 6 `[MVP]` for both pre-game and live in-session authoring (CoW Overlay, Bake to Base World Template, or Spoiler-Free Solo Seed Pins), featuring a location/dungeon stamp palette, portal/staircase/chasm wiring, cascading ontology/tileset inspection, and a no-code **NPC & Companion Mind-Sheet Designer** + **Faction & Progress Clock Designer**.
   - **Zero-AI (`Tier A`) Dialogue Topic-Chip, Bark & Solo Oracle Table Designer (`DialogueAndOracleStudio.tsx`)**: Visually authors disposition-gated NPC conversation topic chips, social contest unlock gates, FTS5 keyword triggers, personality-tagged companion barks, and custom Solo Fate/Meaning/Rumor/Sensory tables (`0` LLM calls).
   - **Automated World, Dungeon & Adventure Consistency Linter (`WorldValidationLinter.tsx`)**: Statically verifies key/lock graph reachability (preventing accidental soft-locks where a key is locked behind its own door), portal/staircase/multi-floor integrity, pinned `.rpgrules` reference validity, and 3-Clue Matrix bottleneck redundancy.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
