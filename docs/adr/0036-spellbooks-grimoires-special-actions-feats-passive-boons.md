# 0036. Spellbooks/Grimoires, Special Actions, Feats, Passive Boons & Reactive Triggers UI

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Architectural Decision #36 (`docs/design/system_design_specification.md`)

## Context & Problem Statement
Architectural design constraint and domain resolution for **Spellbooks/Grimoires, Special Actions, Feats, Passive Boons & Reactive Triggers UI** in Meddah: The Universal Story Engine.

## Decision
**4-Tab Schema-Driven Capabilities Deck & Tactical Action Bar (`capabilities_deck/`)**: **(1) Adaptive Grimoire / Power Manager** (adapts to the active `.rpgrules` magic/power paradigm: *Vancian Slot/Preparation Workbench*, *Mana/Strain/RAM Pool Gauges*, *Roll-to-Cast/Drain*, physical Spellbook/Cyberdeck item binding, Scribe/Learn workflows, Upcasting/Metamagic selectors, and an active **Concentration/Sustained Banner**); **(2) Non-Spell Special Actions, Martial Maneuvers & Active Feats Tab** (grouped by ruleset Action Economy & Category with interactive `1/Rest`, `Recharge`, or Stamina/Ki/Edge pips and drag-to-pin **Bottom Tactical Hotbar `1–0`**); **(3) Passive Boons, Stances & Aura Inspector** (surfaces Innate/Feat Passives, Divine/Patron Boons, Equipment Auras, and Timed Buffs/Conditions with **1-Click Stance/Trade-Off Toggles** [e.g., *Power Attack / Sharpshooter / Thermal Optics*] and hover Formula Breakdown tooltips); and **(4) Reactive Triggers & Interrupt Policy Manager** (lists all `on_targeted / on_hit / on_move / on_spell_cast` reactions with per-ability prompt policies: `Always Ask`, `Ask Only When It Changes Outcome`, `Auto-Trigger`, or `Disabled`).

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Enforced by phase DoD suites (`pytest -m zero_ai`, `tools/lint_agnosticism.py`, `tools/lint_modularity.py`, and `import-linter`) as implementation lands.
