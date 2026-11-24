# 0114. Universal Chase, Pursuit, Race & Moving-Battle Engine (`backend/app/systems/chase_engine.py` & `ScrollingTacticalPursuit.tsx` — Phase 12 & Section 1.27)

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Grill-Me Resolution #64 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Universal Chase, Pursuit, Race & Moving-Battle Engine (`backend/app/systems/chase_engine.py` & `ScrollingTacticalPursuit.tsx` — Phase 12 & Section 1.27)**.

## Decision
- **Dual-Mode Resolution with Auto-Detection & 1-Click Toggle**: Foot pursuits/races, rooftop parkour, sewer flights, and dungeon escapes default to the **Abstract Pursuit & Race Track** (HUD banner above MUD with relative Lead bands `0..N` or interval splits and procedural obstacle cards); mounted cavalry skirmishes, vehicle-to-vehicle highway battles, stagecoach robberies, train shootouts, regattas, and dogfights default to the **2.5D "Scrolling Conveyor" Tactical Canvas** (PixiJS infinite-scrolling canvas with terrain tiles scrolling backward at group velocity and obstacles drifting downfield); GM/players can toggle between views with a 1-click button at any time.
   - **Dual-Mode Resolution with Auto-Detection & 1-Click Toggle**: Foot pursuits/races, rooftop parkour, sewer flights, and dungeon escapes default to the **Abstract Pursuit & Race Track** (HUD banner above MUD with relative Lead bands `0..N` or interval splits and procedural obstacle cards); mounted cavalry skirmishes, vehicle-to-vehicle highway battles, stagecoach robberies, train shootouts, regattas, and dogfights default to the **2.5D "Scrolling Conveyor" Tactical Canvas** (PixiJS infinite-scrolling canvas with terrain tiles scrolling backward at group velocity and obstacles drifting downfield); GM/players can toggle between views with a 1-click button at any time.
   - **Race Mode Topologies & Timing Checkpoints**: Supports both asymmetrical chases and symmetrical/staged races across **Point-to-Point Sprints** (`race_type: "sprint"` with sequential `timing_gate`s, `mandatory_control` inspection/toll gates, branching shortcut forks, and multi-leg endurance service bivouacs) and **Closed-Circuit Laps** (`race_type: "circuit"` with looping sector graphs, `current_lap` vs. `total_laps`, live sector split times $\Delta t$, and photo-finish tiebreakers based on margin of success).
   - **Interactive Pit Stops, Service Bays & Mount Stables**: Racers can diverge into pit lanes, paying a deterministic time/position cost to execute ruleset crew trade checks (Engineering, Mechanics, Animal Handling, Medicine) to repair vehicle hulls, swap tires/treads, clear overheat counters, refuel boosters, or treat mount stamina/fatigue.
   - **Strict Golden-Rule Grounding for Maneuvers & Tactics (Zero Hardcoded Math or Conditions)**: The engine core never hardcodes flat bonuses (`+2`), binary advantage systems, or hardcoded condition tags (`#exhausted`, `blown gaskets`). Instead, all maneuvers hook into native `.rpgrules`: *Drafting/Slipstreaming* triggers the ruleset's native favorable circumstance hook; *Blocking* executes as an authoritative Contested Action window; *Pushing/Overclocking* binds to ruleset-native stress/strain/push hooks or complication stunts; *Weaponized Racing* executes the ruleset's standard combat action economy and damage formulas against target vehicles/entities.
   - **Configurable Party Chase Stances**: At pursuit start, the party selects a stance: **"Stick Together" (Unified Escort)** (party advances at slowest member's speed, faster members grant native ruleset assist/help bonuses on obstacle rolls, members can spend actions to buff/carry/shield, all fight together if cornered) vs. **"Scatter! Every Man for Himself"** (party splits into independent tracks, pursuers divide forces by proximity or bounties, fast PCs can escape early and circle back to set an ambush, cornered PCs face capture or combat alone).
   - **Three Pluggable Action Economy Modes**: Supports three action economy configurations selectable per ruleset or table policy (`chase_action_economy`): **Mode 1: Two-Phase Round** (Phase 1: Movement Maneuver $\rightarrow$ Phase 2: Tactical Action), **Mode 2: Full Action-Tradeoff Economy** (spending native action points between Dash vs. Spells/Attacks), and **Mode 3: Dynamic Chase Action Menu** (Sprint & Dash, Evasive Weave, Create Obstacle, Harassing Attack).
   - **Dynamic Procedural Obstacles & Quarry Active Counter-Play**: Generates setting-grounded complications based on `SettingOntologyBlock` (crowded bazaars, neon gridlock, collapsing sewers) with branching path forks; Quarry can actively manipulate the environment (`> create_obstacle` / MUD & card UI) dropping reactive hazards to penalize pursuers.
   - **Vehicle Crew Stations & Moving Maneuvers**: Full tactical station matrix on the scrolling canvas (Driver/Pilot, Gunner, Navigator, Engineer, Boarder) with ramming, PIT maneuvers, broadsides, vehicle degradation (flat tires, damaged sails, disabled engines), and leaping across moving hulls.
   - **AI Companion Persona Heuristics & Deterministic "Hold the Line" Rearguard Sacrifice**: Companions follow party stances, but high-Trust loyal protectors facing lethal capture trigger a dramatic rearguard hold-the-line prompt—allowing players to accept the sacrifice to escape while spawning a Dynamic Rescue Quest, or refuse to stand and fight together; runs deterministically in Zero-AI mode via `Trust >= 80` + `loyal_guardian` tag + `threat_level: lethal`.
   - **Multi-Faction Relationship Matrix & Roaming Apex Hazards**: Supports $N$ independent entities or factions with a targeted quarry-pursuer graph; wandering beasts or monsters act as **Mobile Dynamic Hazards** on the track attacking whichever entity is closest in Lead bands.
   - **Deterministic End Conditions & Seamless Transitions**: Escape (lead $\ge$ threshold OR broken LoS + Stealth check $\rightarrow$ MUD exploration), Apprehended/Cornered (lead = 0 or cul-de-sac $\rightarrow$ Tactical Combat, Guard Confrontation Flow, or Fail-Forward Capture), Race Podium Settlement (awarding currency/renown), Vehicle Wreck/Crash (grounded skirmish amidst debris), or Surrender/Parley.
   - **100% Ruleset-Agnostic & Admin Configurable**: Binds directly to ruleset driving/athletics/speed stats or progress clocks; `<5ms` deterministic Python/TypeScript execution without LLM compute; all thresholds configurable in `server.toml` (`default_escape_lead_threshold: 5`, `obstacle_spawn_chance_per_zone: 0.35`, `rearguard_trust_threshold: 80`, `race_timing_precision_ms: 10`).

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
