# 0030. Multi-Scale Cyclical Phenomena: Weather, Seasons, Cosmic, Oceanic & Geoactive Worlds

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Architectural Decision #30 (`docs/design/system_design_specification.md`)

## Context & Problem Statement
Architectural design constraint and domain resolution for **Multi-Scale Cyclical Phenomena: Weather, Seasons, Cosmic, Oceanic & Geoactive Worlds** in Meddah: The Universal Story Engine.

## Decision
**Cross-Scale Chronology, Cosmic, Oceanographic & Geoactive Simulation Engine**: **(1) Custom World Calendars, Multi-Scale Seasons & Seasonal Prose Modulation** (seasons, weather, festivals, and time-of-day dynamically shape **deterministic MUD room descriptions** via `seasonal_variants` & indoor/outdoor `exposure_type`, **AI GM & Companion descriptive prose** via a compact 1-line Chronology/Atmosphere stamp in the Micro-Prompt, **JIT room generation**, and **season-cached Scene Backdrops**); **(2) Biome- & Stratum-Aware Dynamic Weather**; **(3) Navigable Moons & Gas Giant Mini-Systems**; and **(4) Optional Paradigm-Agnostic Cyclical Phenomena (`CyclicalPhenomenonBlock`)**—purely modular GM/World-builder tools spanning every scale and Z-stratum, customizable to any setting and 100% grounded in the active ruleset (never assuming mechanics unless defined in `.rpgrules`): **[a] Scale-0 Cosmic, Interstellar & Planar Cycles** (*Hyperspace/Warp Storm Seasons, Rogue Bodies, Binary-Star Seasons, Planar Conjunctions*); **[b] Scale 1–4 Geoactive & Shifting Landscapes** (*Lava Flows/Cooling Crusts, Rising Islands, Shifting Dunes, Glaciers, Seismic Faults*); **[c] Sub-Aquatic (`Z-1 / Z-2`) Oceanographic Cycles** (*Shifting Currents, Thermoclines, Bioluminescent Blooms, Hydrothermal Vents*); and **[d] Subterranean & Sky Strata Cycles** (*Underdark Tides, Spore Blooms, Sky Jetstreams*).

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Enforced by phase DoD suites (`pytest -m zero_ai`, `tools/lint_agnosticism.py`, `tools/lint_modularity.py`, and `import-linter`) as implementation lands.
