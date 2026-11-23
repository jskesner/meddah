# 0007. Inventory, Equipment & Universal Apparel/Cosmetic/Armor Layering

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Architectural Decision #7 (`docs/design/system_design_specification.md`)

## Context & Problem Statement
Architectural design constraint and domain resolution for **Inventory, Equipment & Universal Apparel/Cosmetic/Armor Layering** in Meddah: The Universal Story Engine.

## Decision
**Composable Container & Universal Layered Attachment Graph (`inventory_graph.py`)**: Items/containers support ruleset-defined capacity models (Weight, Slots, 2D Grid, Bulk, Abstract Load), Named Equip/Attachment Nodes, and Passive Modifier Auras while equipped/carried. Includes **Universal Anatomical Slot Binding & Multi-Layer Stacking (`anatomical_slots_and_layering_mode: "abstract_slots" | "anatomical_layered"`)**—completely decoupled from the Hit Location Engine and not restricted to armor: when enabled, **clothing, fashion/cosmetic attire, disguises, jewelry/accessories, climate gear, utility rigs, AND armor** bind to anatomical body locations with multi-location coverage (`covered_locations`) and ordered layers (`undergarment` $\rightarrow$ `inner_clothing` $\rightarrow$ `mid_layer` $\rightarrow$ `protective_armor` $\rightarrow$ `outer_garment_cloak_coat` $\rightarrow$ `cosmetic_accessory_or_transmog_override`), driving paper-doll portrait visuals, social/disguise/concealment tags, climate protection, and armor mitigation.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Enforced by phase DoD suites (`pytest -m zero_ai`, `tools/lint_agnosticism.py`, `tools/lint_modularity.py`, and `import-linter`) as implementation lands.
