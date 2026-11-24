# 0108. Core Development Directive — 100% Deterministic / Zero-AI Usability & Per-Phase Non-AI Testing

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Grill-Me Resolution #58 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Core Development Directive — 100% Deterministic / Zero-AI Usability & Per-Phase Non-AI Testing**.

## Decision
The entire engine across all 14 phases (plus Phase 2.5) must be 100% usable, playable, and feature-complete deterministically with zero AI/LLM providers enabled (`Tier A / Play without AI`). Every AI-assisted capability (ingestion, GM narration, solo play, companion autonomy, quests, world generation, map transposition, ruleset co-design, and media) must provide a complete deterministic counterpart (structured importers/parsers, Solo RPG Oracles & tables, template narration, tactical utility heuristics, visual/manual Studios, and procedural SVG/local audio fallbacks). Every phase must include a dedicated deterministic / non-AI test suite (`pytest -m zero_ai --disable-ai-providers` and E2E `Tier A` tests) in CI to enforce that no feature depends on an LLM to function.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
