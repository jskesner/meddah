# 0032. Loot, Loot Tables & Multiplayer/Companion Loot Distribution

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Architectural Decision #32 (`docs/design/system_design_specification.md`)

## Context & Problem Statement
Architectural design constraint and domain resolution for **Loot, Loot Tables & Multiplayer/Companion Loot Distribution** in Meddah: The Universal Story Engine.

## Decision
**100% Ruleset-Grounded Loot & Distribution Engine**: **(1) Zero-Assumption Loot Representation** (supports itemized gear/currencies, abstract Wealth/Payoff ratings like *Blades in the Dark / Call of Cthulhu*, or zero-loot narrative rulesets—strictly per the active `.rpgrules`); **(2) 5 Universal Loot Generation Sources with Per-Entity & Per-Creature-Type Overrides (`EntityLootConfigBlock`)** (resolved via a 3-tier hierarchy: *Individual Spawned Entity Override $\rightarrow$ Creature Type / Archetype Profile $\rightarrow$ Campaign Default*, allowing multiple loot methods to coexist in the same campaign and encounter: e.g., armed humanoids configured as **Pure WYSIWYG Equipped Drops** [dropping only the actual weapons, armor, clothing, and remaining ammo they carried], beasts/constructs configured as **Skinnable / Harvestable / Salvageable** via ruleset skill/tool checks, bosses/apparitions configured to **Roll Ruleset Nested Loot Tables or Dynamically Spawn Interactive Loot Containers/Chests** when defeated/looted, **GM/Solo Hand-Placed Containers**, and **Quest-Completion Treasure Bundles & Merchant Unlocks (`loot_mode: "treasure_bundles"`)** available across all play modes); **(3) Configurable Multiplayer Distribution Modes** (*Shared Party Treasury + Claim Mode*, *Need / Greed / Pass Roll-Off*, *GM / Party Leader Master Looter*, *Free-for-All / First-Click*, or *Per-Participant Quest Treasure Bundle Payout*); and **(4) AI Companion Loot Desires, Sharing & Dispute Reactions** (companions express interest in items matching their build/personal goals, gain `Trust`/`Affection` when gifted upgrades, and lose `Trust` or trigger a **Contested Confrontation** if a player ninjas/hoards a promised relic or personal quest item).

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Enforced by phase DoD suites (`pytest -m zero_ai`, `tools/lint_agnosticism.py`, `tools/lint_modularity.py`, and `import-linter`) as implementation lands.
