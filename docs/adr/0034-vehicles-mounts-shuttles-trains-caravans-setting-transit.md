# 0034. Vehicles, Mounts, Shuttles, Trains, Caravans & Setting Transit Ontology

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Architectural Decision #34 (`docs/design/system_design_specification.md`)

## Context & Problem Statement
Architectural design constraint and domain resolution for **Vehicles, Mounts, Shuttles, Trains, Caravans & Setting Transit Ontology** in Meddah: The Universal Story Engine.

## Decision
**Multi-Tier Vehicle Spectrum & Setting-Aware Transit Guardrails (`vehicles_and_mounts.py`)**: **(1) Tier-1 Personal & Open-Top Craft (`token_mounted`)** (*Motorcycles, Speeder Bikes, Mounts, Rowboats, Canoes*); **(2) Tier-2 Cabin Craft, Wagons & Shuttles (`cabin_or_token`)** (*Wagons, Stagecoaches with Draft Animals, Sports Cars, Hover Cars, Hot Air Balloons, Orbital Shuttles*—dual 2.5D multi-cell footprint + 1-room MUD cabin + Parent $\leftrightarrow$ Child Docking); **(3) Coupled Trains (`linked_consist`) & Multi-Vehicle Caravans (`multi_vehicle_convoy`)** (**Trains** are linear chains of modular coupled Car Nodes `[Locomotive <-> Tender <-> Coach <-> Vault Car]` moving along `rail_track` edges with roof traversal and live car uncoupling on scrolling rail maps; **Caravans/Convoys** are linked formations of multiple Tier-1/Tier-2 wagons/vehicles and outriders acting as a mobile camp in travel and deploying in Marching or "Circle-the-Wagons" formation on the 2.5D grid); and **(4) Hierarchical Setting & Transit Ontology (`SettingOntologyBlock`)** (when `.rpgrules` does not define vehicle catalogs, the **World $\rightarrow$ Region $\rightarrow$ Settlement/District Ontology** defines `transit_paradigm`, `local_vehicle_catalog`, and `forbidden_anachronisms`—guaranteeing the deterministic spawner, Ambient Ticker, and AI GM Scene Context Header spawn **Hover Cars** in a cyberpunk city and **never** a horse-drawn wagon, while supporting mixed-tech worlds per region/stratum).

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Enforced by phase DoD suites (`pytest -m zero_ai`, `tools/lint_agnosticism.py`, `tools/lint_modularity.py`, and `import-linter`) as implementation lands.
