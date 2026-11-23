# 0028. Rest, Wilderness Camping & Extended Downtime Engine

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Architectural Decision #28 (`docs/design/system_design_specification.md`)

## Context & Problem Statement
Architectural design constraint and domain resolution for **Rest, Wilderness Camping & Extended Downtime Engine** in Meddah: The Universal Story Engine.

## Decision
**100% Ruleset-Defined Recovery, Interactive Camp/Haven RP, GM Safe-Haven Interruptions & Freeform Activity Engine**: **(1) Zero-Assumption Rest & Downtime Building Blocks** (`RestTierBlock` and `DowntimeActivityBlock` extracted by Ingestion Probe #3 or built in the Ruleset Studio); **(2) Context-Sensitive Rest Modes & Granular Settlement Zoning** (**Wilderness/Dungeon Camp** with Watch Shifts/Camp Roles vs. **Settlement/Haven Rest** split into 3 safety tiers: `safe_haven` private quarters with ambient monster suppression, `settlement_public` tavern/bazaar areas with urban disturbance pools, and `settlement_hostile` slum/dock/sewer sectors where active encounter tables and tension pools run continuously); **(3) Authoritative GM Agency & Safe-Haven Interruption Flow** (GMs, AI story pacing, and faction bounty/nemesis callbacks can initiate events and combat encounters anywhere—including nominally "safe" taverns or private bedrooms, such as bar brawls, midnight assassin infiltrations, or guard raids—automatically pausing rest, evaluating ruleset partial recovery if earlier rest tier thresholds were crossed, evaluating unarmored/sleeping readiness via ruleset tags, and offering `[Resume Rest]` or pursuit options); **(4) Interactive "Campfire / Haven Hangout" Phase (Player-Initiated & Companion-Initiated RP)** (before advancing the clock to sleep, the game enters an open-ended **Rest Scene** where players can approach any companion or player to initiate private or group RP conversations, share drinks/stories, gift items, or resolve party tensions); and **(5) Unstructured / Freeform Rest & Downtime Activities** (players and companions are never limited to pre-built buttons—they can type or describe *any* custom duty, hobby, ritual, patrol, or personal activity during rest or downtime, which the AI GM adjudicates narratively and optionally binds to a custom roll, temporary buff, project clock, or memory/relationship update).

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Enforced by phase DoD suites (`pytest -m zero_ai`, `tools/lint_agnosticism.py`, `tools/lint_modularity.py`, and `import-linter`) as implementation lands.
