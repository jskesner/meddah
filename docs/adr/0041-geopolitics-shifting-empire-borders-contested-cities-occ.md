# 0041. Geopolitics, Shifting Empire Borders, Contested Cities, Occupations & Rebellions

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Architectural Decision #41 (`docs/design/system_design_specification.md`)

## Context & Problem Statement
Architectural design constraint and domain resolution for **Geopolitics, Shifting Empire Borders, Contested Cities, Occupations & Rebellions** in Meddah: The Universal Story Engine.

## Decision
**Dynamic Sovereignty, Frontline Warfare & Insurgency Engine (`geopolitics_and_rebellion.py`)**: **(1) Shifting Nation/Empire Boundaries** (`de_jure_sovereign_id` vs. `de_facto_controlling_faction_id` across `Scale 0` star sectors, `Scale 1` continents, and `Scale 2` regional hexes, dynamically redrawing political border polygons, frontier checkpoints, and blockades on the Copy-on-Write Campaign Overlay as regions or fortresses change hands); **(2) Contested Settlements, Cities & Districts ("Split-Control Frontlines")** (divided towns, megacities, or space citadels where Faction A holds certain wards/sectors while Faction B or Rebel Insurgents hold others, separated by **Barricaded No-Man's-Land Streets**, **Sniper Alleys**, and contested **`Z-1` Sewer/Subway Tunnels**); **(3) Military Occupation Mechanics** (automatic swap to **Occupation Martial Law** `JurisdictionLawBlock` with curfews, travel passes, weapon bans, requisitioned shop scarcity, underground resistance black markets, and occupation ambient ticker cues); **(4) 4-Stage Rebellion & Revolt Lifecycle** (`Simmering Discontent` $\rightarrow$ `Underground Insurgency & Sabotage` $\rightarrow$ `Open Street Uprising / City-Wide Siege` $\rightarrow$ `Liberation vs. Brutal Lockdown`); and **(5) Multi-Angle Quest & RP Hooks** (supporting *Freedom Fighter/Rebel*, *Imperial Counter-Insurgency/Peacekeeper*, *Double Agent/Mercenary Profiteer*, or *Kingmaker* playstyles plus AI Companion homeland loyalty/defection stakes).

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Enforced by phase DoD suites (`pytest -m zero_ai`, `tools/lint_agnosticism.py`, `tools/lint_modularity.py`, and `import-linter`) as implementation lands.
