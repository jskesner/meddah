# 0023. Dynamic Party Roster Lifecycle, Mutiny, Defection & Recruitment

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Architectural Decision #23 (`docs/design/system_design_specification.md`)

## Context & Problem Statement
Architectural design constraint and domain resolution for **Dynamic Party Roster Lifecycle, Mutiny, Defection & Recruitment** in Meddah: The Universal Story Engine.

## Decision
**Generalized Companion Social-Consequence & Roster Engine**: **(1) Universal Event Reaction & Confrontation System** (any major player/party action—atrocities, betrayals, loot disputes, faction choices, dialogue—evaluates against all companions' values/memories, potentially triggering RP objections or Contested Social/Combat Checks); **(2) Permanent Departure & Nemesis/Rival Transformation** (if `Trust` drops below critical thresholds or too many negative Core Memories accumulate, a companion can permanently leave and persist in the Living World as a Rival adventurer, join an Enemy Faction, or ally with a Villain—retaining all memories, stats, and gear); **(3) Party Vote to Kick vs. Companion Mutiny** (players can vote to expel a companion with GM override; conversely, if a majority of AI companions despise the player(s), they can stage a **Mutiny** to expel the player(s) or seize the camp/ship/base without ending the campaign); **(4) Continuous Companion Recruitment & Capture/Rescue** (players can recruit new companions at taverns/factions or convert world NPCs when slots open due to death, departure, or capture—with captured companions generating dynamic Rescue Quests); and **(5) Temporary / Quest-Bound Party Members** (`temporary_guest` roster role for escort NPCs, guides, or quest allies who automatically depart when their join condition/quest concludes—or can be invited to join permanently if high Trust was earned).

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Enforced by phase DoD suites (`pytest -m zero_ai`, `tools/lint_agnosticism.py`, `tools/lint_modularity.py`, and `import-linter`) as implementation lands.
