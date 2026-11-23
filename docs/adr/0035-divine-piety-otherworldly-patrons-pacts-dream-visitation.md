# 0035. Divine Piety, Otherworldly Patrons, Pacts & Dream Visitations

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Architectural Decision #35 (`docs/design/system_design_specification.md`)

## Context & Problem Statement
Architectural design constraint and domain resolution for **Divine Piety, Otherworldly Patrons, Pacts & Dream Visitations** in Meddah: The Universal Story Engine.

## Decision
**100% Ruleset-Grounded Higher-Power & Covenant Engine (`piety_and_pacts.py`)**: **(1) Paradigm-Agnostic Higher Powers (`HigherPowerBlock`)** (models *Deities, Pantheons, Warlock Patrons, Great Old Ones, Ancestral Spirits, Rogue AI Overminds, or Syndicate Sponsors* strictly when present in `.rpgrules` or the World Template, with zero forced religion mechanics in secular rulesets); **(2) Dynamic Approval/Piety & Disapproval/Anathema Evaluator** (player actions matching an entity's **Edicts/Tenets** or **Taboos/Anathema** deterministically shift `@covenant.piety` / `@covenant.disapproval`, emit atmospheric omens, unlock tiered ruleset boons, or—when Disapproval reaches critical ruleset thresholds—trigger **Power/Spell Withholding, Divine Curses/Disapproval Tables, Patron Enforcers, or Pact Reckonings**); **(3) Calling Upon Them in Need (`Divine Intervention / Invoke Patron`)** (crisis invocation rolls using ruleset formulas or immediate **In-the-Moment Patron Bargains**); **(4) Dream Visitations & Pact Discussions** (during Rest/Sleep, entities can pull the character into an atmospheric **Dream/Vision Vignette** to discuss/renegotiate their pact or issue **Covenant Quests**); and **(5) Prayer, Rituals & Temple/Sanctum Gameplay** (perform daily devotions/offerings or seek out Churches, Temples, Shrines, and Cult Sanctums for `@spatial.consecrated_ground` bonuses, oracle guidance, Atonement quests, or conversion).

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Enforced by phase DoD suites (`pytest -m zero_ai`, `tools/lint_agnosticism.py`, `tools/lint_modularity.py`, and `import-linter`) as implementation lands.
