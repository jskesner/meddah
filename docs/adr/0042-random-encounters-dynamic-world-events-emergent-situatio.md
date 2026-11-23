# 0042. Random Encounters, Dynamic World Events & Emergent Situations

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Architectural Decision #42 (`docs/design/system_design_specification.md`)

## Context & Problem Statement
Architectural design constraint and domain resolution for **Random Encounters, Dynamic World Events & Emergent Situations** in Meddah: The Universal Story Engine.

## Decision
**Context-Aware Random Encounter & Dynamic Event Director (`random_encounter_and_event_director.py`)**: **(1) 6 Trigger Contexts with Settlement Danger Zoning** (*Overworld Hex-Crawl/Point-to-Point Travel*, *Rest & Night-Watch Interruptions [Wilderness & Haven/Tavern GM Events]*, *Dungeon/Derelict Tension Pool & Wandering Monsters*, *Urban/Megacity Street Events [differentiating `safe_haven` sanctuaries, `settlement_public` social pools, and `settlement_hostile` dangerous districts with full random combat tables]*, *Vehicle/Maritime/Rail/Void Transit*, and *Downtime/Stronghold/Calendar Events*); **(2) 6-Category Non-Trash Taxonomy** (not just combat: **[a] Hostile/Tactical Combat**, **[b] Social/Traveler/Merchant**, **[c] Discovery/Mini-POI Seeds**, **[d] Weather/Environmental Hazards**, **[e] Living Campaign/Faction/Bounty/Companion Callbacks**, and **[f] Atmospheric Omens & Weird Vignettes**); **(3) Pre-Encounter Scouting, Distance, Evasion & Reaction Rolls** (Scout/Lookout spotting distance + pre-engagement choice card [`Observe`, `Evade/Detour`, `Set Ambush`, `Parley`, `Attack`] + ruleset **Monster Reaction/Disposition Rolls** so creatures aren't mindlessly suicidal); **(4) Stateful Ecosystem Depletion** (unique/finite table entries cross off on the Campaign Overlay once slain, befriended, or resolved); and **(5) Configurable Pacing & Anti-Slog Cooldowns**.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Enforced by phase DoD suites (`pytest -m zero_ai`, `tools/lint_agnosticism.py`, `tools/lint_modularity.py`, and `import-linter`) as implementation lands.
