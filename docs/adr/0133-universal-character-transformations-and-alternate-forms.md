# 0133. Universal Character Transformations & Alternate Form Stat Blocks

- **Date**: 2026-11-25
- **Status**: Accepted
- **Deciders**: Maintainers
- **Related Issues / Decisions**: Decision #2 (`docs/design/system_design_specification.md`), ADR-0002, ADR-0094, ADR-0116, ADR-0131, Volume 1 §1.1 (`docs/design/tech_spec_01_core_vm_and_ingestion.md`), Volume 5 §1.29 (`docs/design/tech_spec_05_gameplay_systems_and_anatomy.md`)

## Context & Problem Statement
Many tabletop systems across genres feature characters shifting forms or switching active stat blocks—such as *Wild Shape*, *Polymorph*, *Lycanthropy*, *Vampire Mist*, *Mech/Drone Chassis Swaps*, *Bio-Morphs*, or *Super-Powered Alter Egos*. Hardcoding hit points, mental-vs-physical stat splits, equipment absorption, or anatomy assumptions would violate Golden Rule #1 (`ADR-0128`) and Golden Rule #4 (`ADR-0131`). Furthermore, `OutfitPreset` in `inventory_graph.py` swaps equipped gear rather than character properties, resource pools, tags, or action decks.

## Decision
Add a declarative, ruleset-driven transformation primitive (`FormBlock` and `FormPoolSpec`) paired with pure VM state transitions (`backend/app/ruleset_vm/forms.py`) and an event-sourced `FORM_CHANGED` lifecycle event:
1. **Declarative Ruleset Schema (`FormBlock` & `FormPoolSpec` in `blocks.py`)**:
   - Rulesets declare optional forms inside `RulesetSchema.forms`. When a ruleset defines no forms (`forms == {}`) or an entity is unshifted (`active_form is None`), the subsystem remains completely dormant (`ADR-0131`) with zero runtime side effects.
   - **Property Transformation Modes (`property_mode`)**: `"replace_all"` (full alternate stat block), `"replace_subset"` (swap physical/targeted stats while keeping mental/remaining base stats), and `"delta_overlay"` (`property_deltas` applied cleanly over base stats). Pass 1 derived formulas and Pass 2 modifiers recompute deterministically on top of active form values, optionally suppressing equipped gear auras (`suppress_gear_auras`).
   - **Resource Pool Policies (`FormPoolSpec`)**: Per-pool `"separate_form_pool"` (with configurable `overflow_to_base` damage spillover and `auto_revert_on_zero`), `"shared_base_pool"`, and `"temp_bonus_pool"` (absorbs damage first before spilling onto base pool).
   - **Actions, Tags, Gear & Multi-Phase VTT/Anatomy Hooks**: Supports `"merge"` vs. `"replace"` `action_mode`, `granted_tags`, `blocked_tags`, `gear_handling` (`"merge_into_form" | "keep_worn" | "drop_to_room"`), timed `default_duration_turns`, `size_category`, `portrait_override_ref`, `token_override_ref`, and `anatomy_topology_override` for Phase 10's hit location engine.
2. **Untouched Base State & Replay Determinism (`vm.py` & `forms.py`)**:
   - Base stats (`EntityState.base_properties`) and base pools (`EntityState.pools`) are preserved intact underneath `EntityState.active_form: ActiveFormState | None`.
   - Switching, auto-reverting on form-pool depletion, manual `revert_form`, and timed `tick_active_form` emit atomic `POOL_MODIFIED` and `FORM_CHANGED` events verified identically by `replay_events()` and `state_hash()`.

## Consequences
### Positive
- Supports fantasy shapeshifting, horror lycanthropy, sci-fi chassis swaps, and heroic form toggles uniformly from one generic schema.
- Additive schema fields (`RulesetSchema.forms`, `EntityState.available_forms`, `EntityState.active_form`) remain 100% backward-compatible with `v0.1.0` rulesets and event logs.

### Negative / Trade-offs
- Adds one new schema file (`schemas/form.schema.json`), `"FORM_CHANGED"` event variant, and optional `forms` / `active_form` fields on existing ruleset and event schemas.

### Neutral
- Subsequent phases (Phase 2 Ingestion Probes, Phase 2.5 CLI `form shift`/`revert`, Phase 6 Character Sheet Form Switcher Pill & portrait/token swap, Phase 10 Hit-Location topology swaps) consume `FormBlock` cleanly via `ROADMAP.md`.

## Compliance & Verification
- Verified by `backend/tests/unit/test_forms.py`, `backend/tests/property/test_forms_properties.py`, `tools/generate_types.py --check`, `tools/lint_agnosticism.py`, `pyright` strict mode, and `pytest -m zero_ai`.
