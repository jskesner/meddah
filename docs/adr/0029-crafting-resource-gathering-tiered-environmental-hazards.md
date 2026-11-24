# 0029. Crafting, Resource Gathering & Tiered Environmental Hazards

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Architectural Decision #29 (`docs/design/system_design_specification.md`)

## Context & Problem Statement
Architectural design constraint and domain resolution for **Crafting, Resource Gathering & Tiered Environmental Hazards** in Meddah: The Universal Story Engine.

## Decision
**Ruleset-Defined Hostile Environments (Default-On, Host-Overridable) + Toggleable Survival Mode**: **(1) Ruleset-Defined Hostile Environments (Enforced by Default)** (inherently lethal or physics-altering environments defined by the active ruleset—such as *Hard Vacuum / Decompression*, *Underwater Submersion / Crush Depth*, *Extreme Radiation / Toxic Atmosphere*, *Zero-G / High-G Gravity*, *Magma / Planar Elemental Fire*—are enforced deterministically via Ruleset `ECA` hooks whenever the `environment_hazards` module is active, unless the character has the required protection/life-support; a Host may disable the module, recorded as an audited `MODULE_OVERRIDE`); **(2) 100% Ruleset-Defined Crafting, Merchant Purchasing & Rest/Downtime Foraging** (players and AI Companions can forage/refine materials during rests/downtime **AND purchase or trade for crafting materials, raw/refined components, provisions, and survival gear at appropriate settlement merchants and shops in both Standard and Survival Mode**); **(3) Standard Mode (Abstracted Materials & Rations)** (when Survival Mode is off, crafting inputs and shop stock use *Location Availability, Rarity, and Value Cost*, and sustenance uses simple abstract `"Days of Rations"`); and **(4) Optional Granular "Survival Mode" Toggle** (adds biome-native **Harvestable Resource Nodes** alongside **Itemized Merchant Stock** [so apothecaries, blacksmiths, general stores, and quartermasters stock specific herbs, ores, ingots, timber, and food items based on settlement economy/biome], **Terrestrial Weather/Seasonal Apparel Management**, and **Itemized Food, Water, Spoilage & Campfire Cooking**).

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Enforced by phase DoD suites (`pytest -m zero_ai`, `tools/lint_agnosticism.py`, `tools/lint_modularity.py`, and `import-linter`) as implementation lands.
