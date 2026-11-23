# 0022. Quest Engine, Emergent Side-Quests, Act/Arc Structuring & Episodic Session Planner

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Architectural Decision #22 (`docs/design/system_design_specification.md`)

## Context & Problem Statement
Architectural design constraint and domain resolution for **Quest Engine, Emergent Side-Quests, Act/Arc Structuring & Episodic Session Planner** in Meddah: The Universal Story Engine.

## Decision
**Hierarchical Quest State-Graph, Act/Arc Storyboard & Episodic Session Director (`quest_studio/` & `episode_director.py`)**: **(1) Multi-Tier Quest Architecture** (*Campaign Main Arcs $\rightarrow$ Multi-Stage Quests $\rightarrow$ Emergent Side-Quests & Companion Quests $\rightarrow$ Rumors/Leads*); **(2) Quest Builder with World Map POI Spawning**; **(3) Emergent RP Side-Quest Crystallization**; **(4) Fog-of-War Player Quest Journal**; **(5) Campaign Act/Arc Structuring & Episodic Session Director** (supports **3 Campaign Paradigms**: *(a) Multi-Act Serialized Epics [Seasons $\rightarrow$ Acts I–III $\rightarrow$ Chapters]*, *(b) TV-Style Episodic / Monster-of-the-Week Sessions [`EpisodeBlueprint` with Cold Open + "Previously On..." TTS Recap $\rightarrow$ Briefing/Prep $\rightarrow$ Midpoint Twist $\rightarrow$ Climax $\rightarrow$ Cliffhanger & Between-Episode Downtime Bridge]*, and *(c) Universal Open-Sandbox / West Marches Expeditions* [**the exact same Universal West Marches Campaign Paradigm detailed in Decisions #16 & #47 / §1.6.5**—usable in Solo, Co-Op, Private Hosted Multiplayer, and serving as the exclusive campaign paradigm for Persistent Multi-Player Guild Server Mode]; includes a visual **Act/Arc Thread-Weaving Board**, **1-Click Scene Beat Playlist**, **Real-Time/Turn Pacing Director**, **Fronts/Doomsday Clocks**, and **3-Clue Mystery Matrix**); and **(6) Side-Quest Abandonment, Party Vote & Companion Confrontation System**.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Enforced by phase DoD suites (`pytest -m zero_ai`, `tools/lint_agnosticism.py`, `tools/lint_modularity.py`, and `import-linter`) as implementation lands.
