# 0019. Advanced 2.5D Tactical VTT Engine, Dynamic Rescaling & Modular Cell Hazards

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Architectural Decision #19 (`docs/design/system_design_specification.md`)

## Context & Problem Statement
Architectural design constraint and domain resolution for **Advanced 2.5D Tactical VTT Engine, Dynamic Rescaling & Modular Cell Hazards** in Meddah: The Universal Story Engine.

## Decision
**Ruleset-Driven Spatial, Verticality, Scale Rescaling, Hazard Primitives & Spatial Stress Fixtures**: Full support for 2D/2.5D Square, Hex (Flat/Pointy), and Gridless tactical maps featuring: **(1) Configurable Ruleset Defaults & Live Dynamic Rescaling** (rulesets declare native `cell_distance` [e.g. `5`, `1.5`, `1`, `30`], `distance_unit` [`"ft"`, `"m"`, `"yd"`, `"km"`], and topology, with on-the-fly live GM/Host rescaling via the VTT Scale Pill dropdown or 2-point canvas caliper tool instantly recalculating ranges, AoE stencils, and token movement speeds), **(2) Ray-Cast Line-of-Sight (LoS) & Vision Modes**, **(3) Dynamic Lighting & 3-State Fog of War**, **(4) Directional & Terrain Cover Calculator**, **(5) Interactive AoE Stencils**, **(6) Multi-Waypoint Path Tracing & Dynamic Rulers**, **(7) Vertical Distance / Elevation Representation**, **(8) Paradigm-Agnostic Modular Tactical Hazard Primitives (`TacticalHazardBlock`)** (purely optional GM/Solo tools never locked to any genre template, combining *Elevation/Pit Triggers*, *Progressive Track Zones*, *Directional Force Vectors*, *Scheduled/Rhythmic Triggers*, *Tag-Filtered Suppression/Conductivity Auras*, and *Arbitrary Property/State Mutation Zones* triggered by voluntary or **Forced Movement** and 100% grounded in the active `.rpgrules`), and **(9) Spatial Curveball & Edge-Case Stress Suite (`test_tactical_curveballs.py`)** (validating that generalized spatial primitives resolve unconventional topologies without bespoke engine hacks: *Micro-Arena Wrestling Rings* [elastic rope impulse rebound vectors, $Z+1 \rightarrow Z0$ apron drops, turnbuckles, dense multi-token grapple stacking], *Looping Race Tracks & Velodromes* [seamless seam traversal, cambered banked turns, pit-lane merge triggers, continuous high-velocity collision detection], *Regulation Sports Pitches* [polygon scoring endzones, out-of-bounds whistles, offside raycasts, and interactive 3-state loose/carried/in-flight objective ball tokens], *Colliding & Rotating Moving Platforms* [sub-grid relative velocity frames, moving chasms, rotating wall normals], and *Colossal Climbable Entities* [multi-cell tokens functioning simultaneously as combat targets and climbable 2.5D elevated terrain surfaces]).

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Enforced by phase DoD suites (`pytest -m zero_ai`, `tools/lint_agnosticism.py`, `tools/lint_modularity.py`, and `import-linter`) as implementation lands.
