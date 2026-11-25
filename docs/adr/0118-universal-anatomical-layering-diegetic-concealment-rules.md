# 0118. Universal Anatomical Layering — Diegetic Concealment, Ruleset-Timed Outfit Presets & Optional Cosmetic Transmog (`inventory_graph.py` — Phase 1 & Phase 6 [MVP], Volume 1 §1.1.3)

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Design Resolution #68 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Universal Anatomical Layering — Diegetic Concealment, Ruleset-Timed Outfit Presets & Optional Cosmetic Transmog (`inventory_graph.py` — Phase 1 & Phase 6 [MVP], Volume 1 §1.1.3)**.

## Decision
- **Diegetic Layering & Concealment by Default**: Outer garments (`outer_garment_cloak_coat`) physically cover inner layers (`inner_clothing`, `mid_layer`, `protective_armor`), automatically updating the character's paper-doll portrait/token and concealing inner armor or holstered weapons according to the active ruleset's perception/concealment/bulk rules (or functioning as pure narrative/visual layering when the ruleset defines no concealment math).
   - **Diegetic Layering & Concealment by Default**: Outer garments (`outer_garment_cloak_coat`) physically cover inner layers (`inner_clothing`, `mid_layer`, `protective_armor`), automatically updating the character's paper-doll portrait/token and concealing inner armor or holstered weapons according to the active ruleset's perception/concealment/bulk rules (or functioning as pure narrative/visual layering when the ruleset defines no concealment math).
   - **Saved Outfit & Loadout Presets with Ruleset Don/Doff Timing**: Players can save named multi-layer **Outfit / Loadout Presets** (e.g., *Courtly Ballroom Attire*, *Arctic Expedition Layers*, *Full Combat Rig*) that swap in 1 click during freeform/rest scenes, while automatically enforcing the active ruleset's don/doff action or time costs if triggered during structured combat turns.
   - **Optional Host-Toggled Cosmetic Transmog Override (`cosmetic_transmog_enabled: false` by Default / RAW)**: Non-diegetic cosmetic appearance override slots are disabled by default (Rules as Written), but can be enabled per campaign by the Host/GM for tables that want cosmetic outfit overrides.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
