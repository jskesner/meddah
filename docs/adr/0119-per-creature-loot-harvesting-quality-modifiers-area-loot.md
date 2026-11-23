# 0119. Per-Creature Loot, Harvesting Quality Modifiers, Area Loot Consolidation & Container Persistence (`EntityLootConfigBlock` — Phase 9 [Post-MVP], Volume 5 §1.16)

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Grill-Me Resolution #69 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Per-Creature Loot, Harvesting Quality Modifiers, Area Loot Consolidation & Container Persistence (`EntityLootConfigBlock` — Phase 9 [Post-MVP], Volume 5 §1.16)**.

## Decision
- **100% Ruleset-Driven Yield & Item-Condition Modifiers**: Skinning/harvesting/salvage yields and WYSIWYG dropped item durability only degrade from damage types (e.g., fire, acid, or explosive overkill ruining a pelt) or skill-check degrees of success when explicitly declared in the active ruleset's `HarvestableYieldBlock`—the engine never invents hardcoded elemental ruin penalties.
   - **100% Ruleset-Driven Yield & Item-Condition Modifiers**: Skinning/harvesting/salvage yields and WYSIWYG dropped item durability only degrade from damage types (e.g., fire, acid, or explosive overkill ruining a pelt) or skill-check degrees of success when explicitly declared in the active ruleset's `HarvestableYieldBlock`—the engine never invents hardcoded elemental ruin penalties.
   - **1-Click "Area Loot & Harvest Drawer" Consolidation**: After an encounter, players can click individual corpses/spawned chests OR open the consolidated **Area Loot & Harvest Drawer** listing all nearby searchable bodies, skinnable/salvageable creatures, and dynamically spawned containers in one view.
   - **Configurable Remains & Container Persistence**: In persistent campaigns, unlooted containers and remains stay in the Copy-on-Write world overlay (with optional World Calendar decay ticks for organic corpses while permanent items/chests persist); in ephemeral West Marches instances, unclaimed instance drops resolve or clean up automatically at Atomic Settlement.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
