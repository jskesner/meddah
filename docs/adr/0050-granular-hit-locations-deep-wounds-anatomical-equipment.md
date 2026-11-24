# 0050. Granular Hit Locations, Deep Wounds, Anatomical Equipment Slots, Field Surgery & Prosthetic Retrofits

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Architectural Decision #50 (`docs/design/system_design_specification.md`)

## Context & Problem Statement
Architectural design constraint and domain resolution for **Granular Hit Locations, Deep Wounds, Anatomical Equipment Slots, Field Surgery & Prosthetic Retrofits** in Meddah: The Universal Story Engine.

## Decision
**Universal Body Topology, Wound & Medical Engine (`hit_location_engine.py` & `HitLocationSilhouetteHUD.tsx`)**: **100% Modular, Customizable & Optional Architecture**: Designed as a suite of decoupled, independent opt-in building blocks that scale across ruleset tones—from light-hearted/narrative games (*Toon, Ryuutama, Avatar Legends*, where amputations are strictly disabled, surgery is bypassed, and damage is purely temporary/comedic or simplified rest) to gritty simulationist systems (*Cyberpunk, Warhammer Fantasy, Battletech, RuneQuest*): **(1) Modular Hit Location Topology (`HitLocationTopologyBlock`)** (supports three declarative vitality topologies across Humanoids, Quadrupeds, Avians, Mechs/Vehicles, and Eldritch entities: (a) *Monolithic* [single global vitality pool], (b) *Independent Locations* [pure per-limb health pools with vital location incapacitation], and (c) *Composite Dual* [tracks **both** total entity vitality and individual limb health pools with declarative damage coupling policies such as direct mirroring, excess overflow, or vital-only spillover]); **(2) Untargeted Hit Distribution vs. Called Shots** (declarative dice distribution tables [e.g. `1d20` or reversed percentile digits] for standard attacks + called-shot penalty modifiers); **(3) Universal Anatomical Slots, Clothing/Cosmetic/Armor Layer Stacking & Durability Ablation** (integrates with `inventory_graph.py`'s `anatomical_slots_and_layering_mode: "abstract_slots" | "anatomical_layered"`—usable even when `hit_locations` is disabled: clothing, cosmetics, disguises, accessories, climate gear, and armor bind to body location nodes with multi-location coverage and ordered layer stacking, driving paper-doll visuals, concealment/disguise tags, climate protection, and localized or aggregate armor DR/ablation); **(4) Deep Wounds, Critical Injury Tables & Capability Gating** (customizable: `"none"`, `"cinematic_conditions"` [temporary non-lethal statuses like `#dazed` or `#winded`], or `"granular_tables"` [location-specific trauma]; exceeding major wound thresholds automatically gates dependent capabilities on the Capabilities Deck); **(5) Modular Medical Care & Field Surgery Pipeline** (customizable: `"none"` [arcade/narrative], `"simplified_rest"` [standard rests clear injuries], or `"tiered_surgery"` [active Field Triage, Rest/Downtime surgical checks, and hospital recuperation]); **(6) Decoupled Amputation & Prosthetic Sockets** (`amputation_mechanics: "disabled" | "cinematic_reversible" | "permanent_hardcore"`; narrative/lighthearted games disable permanent limb loss entirely, while gritty systems expose modular prosthetic sockets for peg-legs, clockwork limbs, or cybernetics); and **(7) Dynamic Anatomical Silhouette HUD** (automatically hidden for monolithic/narrative games; displays interactive body-part paper-doll, localized health/armor bars, and visual shaders when hit locations are active).

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Enforced by phase DoD suites (`pytest -m zero_ai`, `tools/lint_agnosticism.py`, `tools/lint_modularity.py`, and `import-linter`) as implementation lands.
