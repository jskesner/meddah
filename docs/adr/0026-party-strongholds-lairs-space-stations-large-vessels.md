# 0026. Party Strongholds, Lairs, Space Stations & Large Vessels

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Architectural Decision #26 (`docs/design/system_design_specification.md`)

## Context & Problem Statement
Architectural design constraint and domain resolution for **Party Strongholds, Lairs, Space Stations & Large Vessels** in Meddah: The Universal Story Engine.

## Decision
**100% Ruleset-Defined Unified Holdings & Vessel Engine**: **(1) Unified Dual-Entity Architecture** (both **Stationary Holdings**—*Keeps, Castles, Secret Underground Lairs, Guildhalls, Outposts, Orbital Space Stations*—and **Mobile Vessels**—*Airships, Galleons, Starships, Walking Cities*—share the exact same engine primitive: a **Ruleset Entity Archetype** paired with a **Persistent Interior Location Sub-Graph**; mobile vessels simply have `can_move: true` while stationary strongholds are anchored to a World/Region/Z-Stratum/Scale-0 coordinate); **(2) Strictly Ruleset-Defined Facilities & Downtime Mechanics** (the engine never assumes stronghold rules—if the active ruleset defines Bastion/Stronghold/Hideout stats like *Defense, Influence, Secrecy/Heat, Treasury, Garrison, Power Grid*, or modular **Facility Rooms** like *Arcane Sanctum, Forges, Medbay, Brig, Hydroponics, Spy Network*, they compile into `HoldingArchetype` and `FacilityBlock` building blocks; otherwise they function as rich narrative bases with persistent storage and resting); **(3) Acquisition & Construction** (Purchase/Land Grant, Clearing & Claiming a Dungeon/Ruin/Station, Building from Scratch via Progress Clocks, or Faction Conquest); and **(4) Base Staff, Garrison & Siege Defense** (assign idle AI Companions and hired NPC specialists to run facilities, generate passive downtime resources/intel, and defend the stronghold on its 2.5D tactical map if raided or besieged).

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Enforced by phase DoD suites (`pytest -m zero_ai`, `tools/lint_agnosticism.py`, `tools/lint_modularity.py`, and `import-linter`) as implementation lands.
