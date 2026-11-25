# 0116. Granular Hit Locations, Three Vitality Topologies, Universal Clothing/Cosmetic/Armor Layering, Deep Wounds, Surgery & Prosthetic Retrofits (`backend/app/systems/hit_location_engine.py` & `HitLocationSilhouetteHUD.tsx` — Phase 10, Section 1.29 & Decision #50)

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Design Resolution #66 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Granular Hit Locations, Three Vitality Topologies, Universal Clothing/Cosmetic/Armor Layering, Deep Wounds, Surgery & Prosthetic Retrofits (`backend/app/systems/hit_location_engine.py` & `HitLocationSilhouetteHUD.tsx` — Phase 10, Section 1.29 & Decision #50)**.

## Decision
- **100% Modular, Customizable & Optional Architecture**: Designed as a suite of decoupled, independent opt-in building blocks that scale across ruleset tones—from light-hearted/narrative games (*Toon, Ryuutama, Avatar Legends*, where amputations are strictly disabled, surgery is bypassed, and damage is purely temporary/comedic or simplified rest) to gritty simulationist systems (*Cyberpunk, Warhammer Fantasy, Battletech, RuneQuest*). Master toggle defaults to `false` (monolithic vitality baseline with zero limb overhead).
   - **100% Modular, Customizable & Optional Architecture**: Designed as a suite of decoupled, independent opt-in building blocks that scale across ruleset tones—from light-hearted/narrative games (*Toon, Ryuutama, Avatar Legends*, where amputations are strictly disabled, surgery is bypassed, and damage is purely temporary/comedic or simplified rest) to gritty simulationist systems (*Cyberpunk, Warhammer Fantasy, Battletech, RuneQuest*). Master toggle defaults to `false` (monolithic vitality baseline with zero limb overhead).
   - **Three Declarative Vitality Topologies (`HitLocationTopologyBlock`)**: Cleanly supports (1) *Monolithic* (single global vitality pool), (2) *Independent Locations* (pure per-limb health pools with vital organ death), and (3) *Composite Dual* (tracks **both** total entity vitality and individual limb health pools with configurable damage coupling like direct mirroring, excess overflow, or vital-only spillover—as seen in *RuneQuest, BRP, Cyberpunk, Warhammer Fantasy, Battletech, Fallout, and Twilight: 2000*) across Humanoids, Quadrupeds, Avians, Mechs/Vehicles, and Eldritch horrors.
   - **Untargeted Hit Distribution vs. Called Shots**: Standard attacks roll against declarative dice distribution tables (e.g. `1d20` or reversed percentile digits); targeted called shots apply ruleset-defined situational difficulty modifiers.
   - **Universal Anatomical Slot Binding & Multi-Layer Apparel/Cosmetic/Armor Stacking (`anatomical_slots_and_layering_mode: "abstract_slots" | "anatomical_layered"`)**: Configured in `inventory_graph.py` (§1.1.3) and **not exclusive to armor or to the Hit Location Engine** (usable even when `hit_locations` is disabled). Clothing, fashion/cosmetic attire, disguises, jewelry/accessories, climate gear, utility rigs, and armor bind to anatomical location nodes with multi-location coverage (`covered_locations`) and ordered layer stacking (`undergarment` $\rightarrow$ `inner_clothing` $\rightarrow$ `mid_layer` $\rightarrow$ `protective_armor` $\rightarrow$ `outer_garment` $\rightarrow$ `cosmetic_accessory_or_transmog_override`)—driving paper-doll visuals, concealment/disguise tags, climate protection, and localized or aggregate armor DR/ablation.
   - **Deep Wounds, Critical Injury Tables & Automatic Capability Gating**: Configurable between *None*, *Cinematic Conditions* (temporary non-lethal tags like `#dazed` or `#winded`), and *Granular Tables* (location trauma tables). Exceeding major wound thresholds automatically disables dependent capabilities on the Capabilities Deck.
   - **Modular Medical Care & Field Surgery Pipeline**: Configurable between *None*, *Simplified Rest* (standard rests clear temporary sprains/strains), and *Tiered Surgery* (Field Triage, Rest/Downtime surgical checks, and hospital recuperation).
   - **Decoupled Amputation & Prosthetic / Augment Sockets**: Configurable via `amputation_mechanics: "disabled" | "cinematic_reversible" | "permanent_hardcore"`. In narrative/lighthearted games, limbs can never be severed. In gritty systems, amputations expose modular prosthetic sockets; transhumanist/sci-fi games can also mount cyberware into modular augment sockets on fully intact bodies without requiring amputation.
   - **Dynamic Anatomical Silhouette HUD & Condition Shaders**: Automatically hidden for monolithic/narrative games; renders an interactive anatomical paper-doll showing localized vitality/armor bars (alongside the global vitality gauge in Composite Dual mode), with dynamic bandages, splints, and cybernetics rendered across portraits and VTT standee tokens.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
