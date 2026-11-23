# 0120. Universal Quest-Completion Treasure Bundles — Configurable Payout Timing & Scoped Merchant Registry Unlocks (`loot_mode: "treasure_bundles"` — Phase 9 [Post-MVP], Volume 5 §1.16)

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Grill-Me Resolution #70 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Universal Quest-Completion Treasure Bundles — Configurable Payout Timing & Scoped Merchant Registry Unlocks (`loot_mode: "treasure_bundles"` — Phase 9 [Post-MVP], Volume 5 §1.16)**.

## Decision
- **Configurable Settlement Timing Across All Campaign Paradigms**: Quests and campaigns configure whether earned **Treasure Bundles** pay out **`instant_on_quest_complete`** (ideal for Episodic Series, Serialized Epics, or abstract Wealth/Payoff rulesets) or remain as **`unbanked_until_haven_or_settlement`** until the party reaches a safe camp rest, settlement, or West Marches Hub.
   - **Configurable Settlement Timing Across All Campaign Paradigms**: Quests and campaigns configure whether earned **Treasure Bundles** pay out **`instant_on_quest_complete`** (ideal for Episodic Series, Serialized Epics, or abstract Wealth/Payoff rulesets) or remain as **`unbanked_until_haven_or_settlement`** until the party reaches a safe camp rest, settlement, or West Marches Hub.
   - **Scoped `UnlockedMerchandiseRegistry` Tagging**: Signature items unlocked by completing quests carry declarative availability scope tags (`scope: "global" | "faction_quartermasters" | "min_settlement_economy_tier" | "specific_vendor_id"`), ensuring unlocked rewards appear at appropriate merchants across any campaign paradigm without forcing every roadside peddler to stock legendary relics.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
