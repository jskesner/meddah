# 0024. Player Death, Companion Resurrection & Campaign Succession

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Architectural Decision #24 (`docs/design/system_design_specification.md`)

## Context & Problem Statement
Architectural design constraint and domain resolution for **Player Death, Companion Resurrection & Campaign Succession** in Meddah: The Universal Story Engine.

## Decision
**Ruleset-Agnostic Revival & Legacy Continuity Engine**: **(1) Emotional & Tactical Companion Reaction to PC Downed/Death** (grief/vengeance buffs, body recovery, or callous abandonment if hated); **(2) Autonomous Companion Resurrection Attempts** (if the active ruleset defines Actions/Items/Rituals tagged with `revive`/`resurrect` and `Trust`/`Respect` is sufficient, companions automatically attempt in-combat revival or carry the fallen PC to a temple/healer to pay for resurrection); and **(3) Non-Game-Over Solo & Multiplayer Succession** (permanent PC death never ends the campaign—the player can either **Create a New Successor Character** who joins the surviving party or enters the living world, **Assume Direct Control of a Surviving AI Companion** [Solo or GM-approved], or **Rewind via Timeline Checkpoints**—where **in Multiplayer sessions, any Timeline Rewind after character death is strictly gated and can only be initiated or approved with explicit permission from the GM or Host**).

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Enforced by phase DoD suites (`pytest -m zero_ai`, `tools/lint_agnosticism.py`, `tools/lint_modularity.py`, and `import-linter`) as implementation lands.
