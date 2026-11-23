# 0027. Mass Combat, Sieges, Fleet Actions & Battlefield Hazards

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Architectural Decision #27 (`docs/design/system_design_specification.md`)

## Context & Problem Statement
Architectural design constraint and domain resolution for **Mass Combat, Sieges, Fleet Actions & Battlefield Hazards** in Meddah: The Universal Story Engine.

## Decision
**Ruleset-Driven Multi-Scale Warfare, Formation & Modular Battlefield Hazard Engine**: **(1) Full Tactical Map Support Across Scales** (**Skirmish Scale** [5ft], **Battlefield / Grand Tactical Scale** [50yd–1km, Regiments/Formations/Siege Engines], and **Naval/Void Fleet Scale** [Warships/Strike Wings]); **(2) Optional Paradigm-Agnostic Battlefield Hazards (`BattlefieldHazardBlock`)** (purely optional GM/Solo tools built from universal terrain, obstacle, and AoE primitives—freely re-themeable for any setting as *Engineered Field Defenses* [stakes, trenches, minefields, orbital buoys], *Natural Terrain Hazards* [bogs, shoals, asteroid fields, gravity wells], or *Dynamic Mid-Battle Scarring* [crater zones, fire/smoke screens, drifting wreckage]); **(3) Commander Attachment & Dual-Layer Heroic Spotlight Zoom**; **(4) Offensive Sieges**; and **(5) 100% Ruleset-Grounded** (never locked to a genre paradigm and never forcing math/conditions not defined in the active `.rpgrules`).

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Enforced by phase DoD suites (`pytest -m zero_ai`, `tools/lint_agnosticism.py`, `tools/lint_modularity.py`, and `import-linter`) as implementation lands.
