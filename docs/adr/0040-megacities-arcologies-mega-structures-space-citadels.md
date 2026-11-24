# 0040. Megacities, Arcologies, Mega-Structures & Space Citadels

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Architectural Decision #40 (`docs/design/system_design_specification.md`)

## Context & Problem Statement
Architectural design constraint and domain resolution for **Megacities, Arcologies, Mega-Structures & Space Citadels** in Meddah: The Universal Story Engine.

## Decision
**Elastic Multi-Scale Urban & Mega-Structure Engine (`megacity_and_citadel_engine.py`)**: **(1) City-as-World Scale Elasticity** (a sprawling *Fantasy/Planar Metropolis [Waterdeep/Sigil/Sharn/Doskvol]*, *Cyberpunk Megacity/Hive-Spire*, or *Sci-Fi Space Citadel/Ringworld/Generation Ship* can exist as a `Scale 2/3` hub inside a larger world **OR** promote to the top-level `Scale 1` campaign map divided into **Boroughs/Sectors/Ring-Arms [`Scale 2`] $\rightarrow$ Wards/Neighborhoods/Decks [`Scale 3`] $\rightarrow$ Street Blocks & Interiors [`Scale 4`]** with Lazy/JIT street & building expansion); **(2) 5-Layer Vertical Urban Z-Strata** (`Z+2 Upper Spires/Command Rings` $\leftrightarrow$ `Z+1 Sky-Bridges/Monorails` $\leftrightarrow$ `Z0 Street/Promenade` $\leftrightarrow$ `Z-1 Sewers/Subways/Maintenance Tubes` $\leftrightarrow$ `Z-2 Underhive/Buried Ruins/Reactor Core`); **(3) Directional Overworld $\leftrightarrow$ Megacity Gateway Transitions** (multi-hex/multi-vector approach mapping where *North Road $\rightarrow$ Northgate Ward*, *Sea Route $\rightarrow$ Harbor Docks*, *Rail $\rightarrow$ Central Terminus*, *`Z+1/Z+2` Flight/Orbit $\rightarrow$ Sky-Docks/Orbital Ring*, and *`Z-1` Sewers/Underdark $\rightarrow$ Smuggler Outfall*, with gatehouse customs/tolls, mount/wagon stabling, and 1-click outbound journey plotting); **(4) Intra-City Transit & Faction Turf Overlay**; and **(5) Space Citadel Systems** (Docking Bays/Customs, per-sector Life Support/Gravity/Bulkhead isolation).

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Enforced by phase DoD suites (`pytest -m zero_ai`, `tools/lint_agnosticism.py`, `tools/lint_modularity.py`, and `import-linter`) as implementation lands.
