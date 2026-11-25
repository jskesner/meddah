# 0115. Universal Competition, Minigame & Festival Circuit Engine (`backend/app/systems/competition_engine.py` & `CompetitionStageModal.tsx` — Phase 12 & Section 1.28)

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Design Resolution #65 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Universal Competition, Minigame & Festival Circuit Engine (`backend/app/systems/competition_engine.py` & `CompetitionStageModal.tsx` — Phase 12 & Section 1.28)**.

## Decision
- **Six Universal Mechanical Contest Paradigms (`CompetitionEventBlock`)**: Decomposes all sports, festival contests, and tavern games into 6 declarative primitives: (1) *Opposed Tug / Balance Meter* (arm wrestling, tug-of-war, legal trials), (2) *Target Accumulator* (archery, darts, axe throwing, ski tricks, eating contests), (3) *Elimination Bracket Tournament* (jousting, martial arts, duels), (4) *Escalating Attrition / Last Man Standing* (drinking contests, cold plunges, endurance trials), (5) *Micro-Spatial Board* (billiards, pool, shuffleboard, curling, bocce), and (6) *Wager Card & Dice Table* (poker, blackjack, liar's dice, shell games).
   - **Six Universal Mechanical Contest Paradigms (`CompetitionEventBlock`)**: Decomposes all sports, festival contests, and tavern games into 6 declarative primitives: (1) *Opposed Tug / Balance Meter* (arm wrestling, tug-of-war, legal trials), (2) *Target Accumulator* (archery, darts, axe throwing, ski tricks, eating contests), (3) *Elimination Bracket Tournament* (jousting, martial arts, duels), (4) *Escalating Attrition / Last Man Standing* (drinking contests, cold plunges, endurance trials), (5) *Micro-Spatial Board* (billiards, pool, shuffleboard, curling, bocce), and (6) *Wager Card & Dice Table* (poker, blackjack, liar's dice, shell games).
   - **Multi-Event Festival & Decathlon Circuits (`FestivalCircuitBlock`)**: Links multiple distinct minigames under a unified festival schedule with an overall Championship Points Table, allowing players to explore festival grounds freely between events while competing for the Grand Champion crown, settlement renown, and festival buffs.
   - **First-Class "Foul Play" & Sabotage Pipeline**: Participants can attempt covert cheating, spiked drinks, rigged gear, and sleight of hand via contested ruleset checks (Stealth/Thievery vs. Referee & Spectator Perception), risking instant disqualification, fines, legal warrants, or tavern brawl escalation.
   - **Integrated Spectator Wagering & Sideline Agency**: Non-competing party members place bets via an automated Bookmaker HUD (fixed odds, dynamic pari-mutuel pots, or round-by-round side bets) while taking active crowd actions (cheering for morale buffs, heckling rivals, or casting subtle spells from the crowd).
   - **Dual Resolution for Spatial Boards**: Desktop/web clients feature interactive 2D cue/aim physics vectors scaled by character skill modifiers; meanwhile, Terminal MUD mode, headless servers, or players preferring pure tabletop mechanics resolve shots via deterministic ruleset skill checks against table angles and pocket zones with zero GPU requirements.
   - **Autonomous Companion Festival Agency & Dynamic Rivalries**: AI Companions proactively propose entering contests matching their archetypes, form playful rivalries if paired against PCs, celebrate shared victories, and update episodic memories and relationship affinity deterministically in Zero-AI mode via persona tags.
   - **Strict Golden-Rule Grounding & Live Studio**: Zero hardcoded math, stats, or DCs; binds strictly to native `.rpgrules` capabilities; runs deterministically in `<5ms`; and provides a 1-click GM Studio creation wizard for custom `.rpgcompetition` templates.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
