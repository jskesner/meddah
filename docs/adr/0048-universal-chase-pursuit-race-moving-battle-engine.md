# 0048. Universal Chase, Pursuit, Race & Moving-Battle Engine

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Architectural Decision #48 (`docs/design/system_design_specification.md`)

## Context & Problem Statement
Architectural design constraint and domain resolution for **Universal Chase, Pursuit, Race & Moving-Battle Engine** in Meddah: The Universal Story Engine.

## Decision
**Ruleset-Agnostic Dual-Mode Pursuit & Racing Architecture (`chase_engine.py` & `ScrollingTacticalPursuit.tsx`)**: **(1) Dual-Mode Resolution with Auto-Detection & 1-Click Toggle** (foot chases/races, rooftops, sewers, and dungeon escapes default to the **Abstract Pursuit Track** with lead bands/splits and procedural obstacle cards; mounted cavalry, highway battles, train shootouts, regattas, and dogfights default to the **2.5D "Scrolling Conveyor" Tactical Canvas** with infinite scrolling terrain and procedural road hazards drifting downfield, with 1-click live GM/player view switching); **(2) Race Mode, Track Topologies & Timing Checkpoints** (supports both asymmetrical chases and symmetrical/staged races across **Point-to-Point Sprints** [with sequential timing gates, mandatory control checkpoints, branching shortcut forks, and endurance service bivouacs] and **Closed-Circuit Lap Tracks** [looping sector graphs with `current_lap` counters, live Sector Split Times $\Delta t$, and deterministic photo-finish tiebreakers]); **(3) Interactive Pit Stops & Maintenance Bays** (racers can diverge into pit lanes, paying a deterministic time/position cost to execute ruleset crew skill checks for hull/vehicle repair, tire/gear swaps, engine cooling, or mount stamina/exhaustion recovery); **(4) Strict Golden-Rule Grounded Maneuvers & Tactics** (zero hardcoded math: *Drafting/Slipstreaming* hooks into ruleset-native circumstance modifiers; *Blocking* executes as native Contested Actions; *Pushing/Overclocking* invokes native ruleset stress/strain/push hooks or complication stunts; *Weaponized Racing* executes native ruleset combat actions and damage formulas); **(5) Configurable Party Chase Stances** (**"Stick Together"** [moves at slowest member's speed with mutual assist advantage on obstacle rolls and buff/carry actions] vs. **"Scatter! Every Man for Himself"** [splits into independent tracks forcing pursuers to divide forces by proximity or bounties]); **(6) Three Pluggable Action Economy Modes** (Two-Phase Round, Full Action-Tradeoff Economy, or Dynamic Choice Menu); **(7) AI Companion Persona Heuristics & Deterministic Rearguard Sacrifice ("Hold the Line")** (`Trust >= 80` + `loyal_guardian` tag + `threat_level: lethal` prompt card); and **(8) Multi-Faction Relationship Matrix & Roaming Apex Hazards** ($N$ independent entities/factions plus wandering mobile hazards).

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Enforced by phase DoD suites (`pytest -m zero_ai`, `tools/lint_agnosticism.py`, `tools/lint_modularity.py`, and `import-linter`) as implementation lands.
