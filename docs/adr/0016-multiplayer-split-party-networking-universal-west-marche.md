# 0016. Multiplayer Split-Party, Networking & Universal West Marches Paradigm

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Architectural Decision #16 (`docs/design/system_design_specification.md`)

## Context & Problem Statement
Architectural design constraint and domain resolution for **Multiplayer Split-Party, Networking & Universal West Marches Paradigm** in Meddah: The Universal Story Engine.

## Decision
**Multi-Room Party Support + Zero-Config Tunnel/Invite Codes + Universal West Marches Expedition Paradigm**: Per-character room tracking allows split parties with isolated logs/fog-of-war; disconnected players hand off to Follow/AI-Autopilot/GM control; networking supports both Direct IP and one-click Tunnel/Invite Codes with a Host Waiting Room. Universal **West Marches Campaign Paradigm** (applicable to **any play mode or campaign**—Solo Play, GMless Co-Op, Private Host-Authoritative Multiplayer on Desktop/Web, or 24/7 Guild Server; because West Marches is the **only** campaign paradigm currently planned for Persistent Multi-Player Guild Server Mode, it also incorporates purpose-built server multiplayer optimizations that are enforced in `guild-server` mode and individually optional in solo/private campaigns): **(1) Scale-Elastic & Multi-Scale Hub Topology (`Scale 0` through `Scale 4`)** (expands the traditional frontier town hub concept across all Meddah scales: *Scale 4/3 District/Station Hubs* [safe megacity blocks, underground hacker speakeasies, orbital stations, citadel wards], *Scale 2 Regional/System Hubs* [demilitarized valleys, sovereign baronies, civilized solar systems/asteroid belts], *Scale 1 Continental & Core World Hubs* [planetary ecumenopolises, civilized core star sectors], and *Scale 0 Persistent Hub Timelines, Multiverse Universes & Pan-Dimensional Nexus Citadels* [immutable Prime Timelines, End-of-Time sanctuaries, and dimensional crossroads cities where expeditions venture into alternate timelines, parallel dimensions, or quantum branches, with emergency *Chronal/Dimensional Tether Retrieval*], plus *Hierarchical "Hub-and-Spoke" Nested Hub Networks* with shared or local merchandise registries and scale-aware cartography/travel watch engines); **(2) Hybrid Expedition Initiation** (accept targeted Bounty Contracts for bounded instances OR embark on open-ended **Frontier Scouting Expeditions** into overworld hexes with Travel Watches, survival navigation, push-your-luck danger scaling, and collective cartography mapping, strictly using ruleset-defined travel/sustenance rules or abstract ticks); **(3) Long Multi-Stage & Multi-Location Quests** with Stage Checkpoints in personal Quest Journals (parties can return to the hub between stages to resupply and bank progress, allowing substitute party members between sessions); **(4) Hub-Based Urban & Social Quests** (`QuestStateEvaluator` client-scoped quest overlays allowing shared-room NPC dialogue and clue inspections without collisions or despawning props); **(5) 4-Tier Item Scoping** (`persistent`, `instance_local`, `quest_objective`, `mission_reward`) protecting the persistent hub economy; **(6) Configurable Defeat Policy** (defaulting to "Guild Rescue & Recovery Debt" where fallen PCs wake in the Hub Infirmary with persistent gear intact and vitality restored per ruleset rest rules, but forfeit unbanked instance rewards and incur medical debt/recovery debuffs per campaign policy); **(7) Dual-Tier Housing & Facilities** (personal apartments/homes + shared Guild Halls with container permissions and facility boons); **(8) Housing to Mobile Vessel Conversion** (using the Unified Dual-Entity `HoldingArchetype` with `can_move: true` preserving 100% of interior decor, rooms, and storage, with hub mooring slips and mobile forward base capabilities); and **(9) Progression Tier Metric (`ProgressionTierMetric`)** (normalizing power levels across level-based, skill-tick, karma, and narrative playbook systems for quest gating).

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Enforced by phase DoD suites (`pytest -m zero_ai`, `tools/lint_agnosticism.py`, `tools/lint_modularity.py`, and `import-linter`) as implementation lands.
