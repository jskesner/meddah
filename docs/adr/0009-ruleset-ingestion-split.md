# 0009. Ruleset Ingestion Split

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Architectural Decision #9 (`docs/design/system_design_specification.md`)

## Context & Problem Statement
Architectural design constraint and domain resolution for **Ruleset Ingestion Split** in Meddah: The Universal Story Engine.

## Decision
**Hybrid Structured Mechanics + 14-Domain Semantic Lifecycle Probes + Indexed Compendium**: Core stats, dice mechanics, conditions, and primary actions compile immediately into strict VM blocks; a dedicated **14-Domain Semantic & Lifecycle Probe Pass (`lifecycle_probes.py`)** actively scans ingested sources for *(1) Vitality/Dying/Death*, *(2) Stabilization/Resurrection/Restoration*, *(3) Rest/Downtime/Recovery*, *(4) Character Creation & Advancement*, *(5) Tactical Spatial/Cover/2.5D Elevation*, *(6) World Cosmology/Scales 0–4/Z-Strata/Megacities*, *(7) Social/Morale/Sanity/Faction Rep*, *(8) Spells/Stances/Reactions/Resource Pools (Capabilities Deck)*, *(9) Retinue/Pets/Mounts/Drones/Minions*, *(10) Vehicles/Caravans/Setting Ontology*, *(11) Holdings/Strongholds/Mass Warfare*, *(12) Crafting/Traps/Survival/Economy*, *(13) Overworld Travel/Multi-Floor Dungeons/Random Tables*, and *(14) Deities/Piety/Oaths/Dreams & Law/Crime/Capture* (explicitly marking missing domains `none/absent` under the Zero-Assumption Guarantee); large catalogs index into Vector/FTS storage with **On-Demand JIT Compilation**.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Enforced by phase DoD suites (`pytest -m zero_ai`, `tools/lint_agnosticism.py`, `tools/lint_modularity.py`, and `import-linter`) as implementation lands.
