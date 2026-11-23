# 0049. Universal Competition, Minigame & Festival Circuit Engine

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Architectural Decision #49 (`docs/design/system_design_specification.md`)

## Context & Problem Statement
Architectural design constraint and domain resolution for **Universal Competition, Minigame & Festival Circuit Engine** in Meddah: The Universal Story Engine.

## Decision
**Ludological Contest Primitives & Modular Minigame Architecture (`competition_engine.py` & `CompetitionStageModal.tsx`)**: **(1) Six Universal Mechanical Contest Paradigms (`CompetitionEventBlock`)** covering virtually all sports, festival contests, and tavern minigames: *Opposed Tug / Balance Meter* (arm wrestling, tug-of-war, debate), *Score / Target Accumulator* (archery, darts, axe throwing, ski tricks, eating contests), *Elimination Bracket Tournament* (jousting, martial sparring, duels), *Escalating Attrition / Last Man Standing* (drinking contests, cold plunges, endurance trials), *Micro-Spatial 2.5D Board* (billiards, pool, shuffleboard, curling, bocce), and *Wager Card & Dice Table* (poker, liar's dice, craps, shell games); **(2) Multi-Event Festival & Decathlon Circuits (`FestivalCircuitBlock`)** (groups multiple minigames under a unified festival schedule, calculating overall Championship Points while players freely explore festival grounds); **(3) First-Class "Foul Play" & Sabotage Pipeline** (covert cheating, spiked drinks, rigged gear, and sleight of hand via contested ruleset checks [Stealth/Thievery vs. Referee & Spectator Perception], risking disqualification, fines, or tavern brawl escalation); **(4) Integrated Spectator Wagering & Sideline Agency** (non-competing party members and spectators place bets via an automated Bookmaker HUD with fixed or pari-mutuel odds, while taking active sideline actions: cheering for morale buffs, heckling rivals, or casting subtle spells); **(5) Dual Resolution for Spatial Boards** (interactive 2D aim/physics vector canvas on desktop/web scaled by character skill modifiers, paired with a deterministic ruleset skill check fallback for headless servers, Terminal MUD mode, or pure tabletop preference); **(6) Autonomous Companion Festival Agency & Dynamic Rivalries** (companions proactively enter contests matching their archetypes, form playful rivalries against PCs, and update episodic memories and relationship affinity deterministically in Zero-AI mode); and **(7) Strict Golden-Rule Grounding & Live Studio** (zero hardcoded math or genre terms; binds strictly to native `.rpgrules` capabilities; `<5ms` deterministic resolution; 1-click GM Studio creation).

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Enforced by phase DoD suites (`pytest -m zero_ai`, `tools/lint_agnosticism.py`, `tools/lint_modularity.py`, and `import-linter`) as implementation lands.
