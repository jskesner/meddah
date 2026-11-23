# 0046. AI GM Difficulty Scaling, Roll Fudging, Hints & Anti-TPK Director

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Architectural Decision #46 (`docs/design/system_design_specification.md`)

## Context & Problem Statement
Architectural design constraint and domain resolution for **AI GM Difficulty Scaling, Roll Fudging, Hints & Anti-TPK Director** in Meddah: The Universal Story Engine.

## Decision
**Configurable GM Leniency, Pacing & Mercy Engine (`gm_difficulty_and_mercy_director.py` — Defaults to Rules as Written)**: Strictly defaults to **`Rules as Written (RAW) / Unmodified Referee [Default]`** across all five controls (with *Balanced Tabletop GM*, *Story-First / Merciful*, and *Tactical Challenge* as opt-in presets): **(1) 3 Encounter Scaling Modes** (`Static World-Authentic / Rules as Written [Default]`, opt-in `Bounded Regional Band Scaling`, or opt-in `Party-Balanced Budget Scaling`); **(2) Dice Visibility & Roll Fudging** (`Open Table / Zero Fudging [Default]`, `Hidden Screen / Honest Rolls`, or opt-in `Merciful GM Screen` with trash-mob lethal-crit dampening, bad-luck streak breakers, and ruleset minimum-survivable state clamping); **(3) Multi-Tier Hint & Warning System** (`Rules as Written Passive/Active Checks Only [Default]`, opt-in diegetic Companion/Familiar puzzle nudges & *"Are you sure?"* lethality warnings, and opt-in `[Ask GM for a Hint 💡]` 3-stage hints); **(4) Enemy Tactical Behavior** (`Archetype-Authentic / Rules as Written [Default]`, or opt-in `Wargame Ruthlessness` / `Tabletop Cinematic` / `Pulp Forgiving`); and **(5) Anti-TPK Policy** (`Rules as Written / No Artificial Intervention [Default]`, or opt-in **Fail-Forward Capture/Surrender Offers** [Section 1.21.5], **Villain Objective / Morale Exits**, or **Patron/Cavalry Miracles** with narrative debt).

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Enforced by phase DoD suites (`pytest -m zero_ai`, `tools/lint_agnosticism.py`, `tools/lint_modularity.py`, and `import-linter`) as implementation lands.
