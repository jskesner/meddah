# 0128. Golden Rule #1: Zero-Assumption Agnosticism

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Golden Rule #1 (`docs/design/system_design_specification.md`)

## Context & Problem Statement
Non-negotiable invariant defining **Golden Rule #1: Zero-Assumption Agnosticism** across all engine layers and phases.

## Decision
The engine core knows **nothing** about "Hit Points", "Armor Class", "Strength", "Spell Slots", "Levels", "Classes", or "d20s". Instead, the engine is a **Universal State & Resolution Virtual Machine** that executes user-defined or AI-extracted **Ruleset Schemas**.
* Whether a ruleset uses d20 roll-over, d100 roll-under, dice pools with symbols/successes, 2d6 narrative tiers + progress clocks, resource bidding, or card draws, the engine processes it through universal building blocks.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Enforced continuously in CI via `tools/lint_agnosticism.py`, `tools/lint_modularity.py`, `import-linter`, and `pytest -m zero_ai`.
