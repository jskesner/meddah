# 0129. Golden Rule #2: 100% Deterministic & Zero-AI Usability Directive + Runtime Auto-Fallback

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Golden Rule #2 (`docs/design/system_design_specification.md`)

## Context & Problem Statement
Non-negotiable invariant defining **Golden Rule #2: 100% Deterministic & Zero-AI Usability Directive + Runtime Auto-Fallback** across all engine layers and phases.

## Decision
The **entire engine**—across all 14 phases (Contiguous MVP Phases 1–6 + Phase 2.5 Slice, and Post-MVP Modular Expansion Phases 7–14), Studios, Solo/GM modes, Multiplayer, World Simulation, Companions/Retinue, Quests, Encounters, Cartography, and Media—must be **100% usable, playable, and feature-complete deterministically with zero AI/LLM providers enabled (`Tier A / Play without AI`) OR when a configured AI provider becomes unavailable mid-session**:
* **Complete Deterministic Counterparts**: Every AI-assisted capability has a first-class deterministic engine counterpart (structured regex/table/FTS5 document parsers, 5-step parameterized ruleset/character wizards, deterministic verb/skill intent matchers, 1-click improvised stunt cards, topic-chip + FTS5 NPC dialogue brokers, structured `DeedFact` campaign ledgers, Solo RPG Oracle/Fate tables, persona-tagged dialogue/bark trees, procedural WFC/tileset JIT room generators, OpenCV `cv2.inpaint` map transposition, and OS-native/procedural SVG media fallbacks).
* **Seamless Runtime Circuit-Breaker Failover (`ai_fallback_router.py`)**: If a session is running with a Local (`Tier B`) or Cloud (`Tier C`) AI provider and that provider becomes unreachable, times out, returns `429`/`5xx`, or hits the user's token/cost budget cap, the **AI Fallback Router** immediately intercepts the failure, routes the request to the deterministic engine counterpart with zero turn loss or crash, displays a non-blocking `[AI Unavailable -> Using Deterministic Engine]` status pill in the top bar, and automatically recovers when the provider is healthy again.
* **Mandatory Per-Phase Enforcement**: Every single development phase is gated by a mandatory **Deterministic / Non-AI Test Suite (`pytest -m zero_ai`)** that runs with all AI providers disabled—plus circuit-breaker failover tests—verifying that every capability functions end-to-end without a single LLM or external model call.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Enforced continuously in CI via `tools/lint_agnosticism.py`, `tools/lint_modularity.py`, `import-linter`, and `pytest -m zero_ai`.
