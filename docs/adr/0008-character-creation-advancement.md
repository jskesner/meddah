# 0008. Character Creation & Advancement

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Architectural Decision #8 (`docs/design/system_design_specification.md`)

## Context & Problem Statement
Architectural design constraint and domain resolution for **Character Creation & Advancement** in Meddah: The Universal Story Engine.

## Decision
**Ruleset State-Graph Engine + 3-Mode Builder & Advancement GUI (`advancement.py` & `character_builder/`)**: **(1) 5 Creation Node Primitives (`creation_graph`)** (`point_buy_pool` with custom cost tables, `standard_array_assign`, `random_roll_assign` [in-order or pool], `package_pick` [Ancestry/Class/Occupation/Playbook bundles with prerequisites & sub-choices], and `lifepath_chain` [multi-term career/event rolls like *Traveller/Cyberpunk*], plus Starting Loadout/Shop & Persona/Covenant setup); **(2) 5 Progression Paradigms (`advancement_graph`)** (**Tiered Level/Milestone Graph**, **Classless XP/Karma Point-Buy Store**, **Usage-Driven Skill Tick Marks & Roll-to-Improve** [e.g. *BRP/Call of Cthulhu*], **Narrative Playbook XP Triggers/Clocks** [e.g. *PbtA/FitD*], and **Diegetic In-World Training/Augmentation**); and **(3) Dual Creation & Progression GUI** (supports **Step-by-Step Guided Wizard** with live Derived-Stat Preview, **Conversational AI "Session Zero" Co-Creator**, and **Veteran Direct-Sheet Editor**, plus an in-campaign **Advancement Drawer** with Before $\rightarrow$ After stat diffing and Event-Sourced audit logging).

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Enforced by phase DoD suites (`pytest -m zero_ai`, `tools/lint_agnosticism.py`, `tools/lint_modularity.py`, and `import-linter`) as implementation lands.
