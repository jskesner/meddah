# 0135. Registered Disguise Slots, Stealth Alignment & Hybrid Synchronized Time Skips

- **Date**: 2026-11-25
- **Status**: Accepted
- **Deciders**: User, Antigravity Agent
- **Related Issues / Decisions**: Golden Rule #1 (`ADR-0128`), Golden Rule #4 (`ADR-0131`), `ADR-0134`, Volume 1 §1.1.4B & §1.1.4C (`docs/design/tech_spec_01_core_vm_and_ingestion.md`), Volume 3 §1.5.6–§1.5.7 (`docs/design/tech_spec_03_world_cosmology_and_society.md`), Volume 4 §1.6–§1.7 (`docs/design/tech_spec_04_multiplayer_ui_and_vtt.md`), Volume 5 §1.13 (`docs/design/tech_spec_05_gameplay_systems_and_anatomy.md`)

## Context & Problem Statement
Building on `ADR-0134`, three needs emerged before beginning Phase 2B:
1. **Registered Disguise Slots (`DisguisePreset`)**: Players with disguise access need a Wardrobe UI and MUD command family (`disguise list/save/don/swap/remove`) to assemble and swap saved persona bundles (alias, presented tags, portrait/token overrides, voice modulation, linked `OutfitPreset`, and required kit items), while respecting ruleset-defined donning durations when an active ruleset requires time to prepare a disguise.
2. **Stealth Pillar Alignment**: Strictly auditing `StealthPillarConfig` against diverse tabletop systems exposed four gaps: (a) unhidden entities without explicit `awareness_map` entries defaulted `get_awareness_level()` to `unaware_level` instead of `detected_level`, (b) ruleset formulas and action requirements (`ActionBlock.requires`, `OutcomeTier.condition`, `EventHookBlock.condition`) could not inspect `@awareness.*` or a cached `@self.stealth_score` / `@target.stealth_score`, (c) visibility checks supported only a single `detected_level` rather than configurable `visible_levels`, and (d) ruleset special senses (`sensory_bypass_tags`) had no declarative schema mapping.
3. **Multiplayer & Split-Party Synchronized Time Skips**: When a timed action (such as donning a disguise, treating wounds, or conducting a short rest of `1m`–`60m`) requests a time skip, other seats need the option to approve, schedule a concurrent activity for that window, hold to act first, or let the GM trigger/interrupt skips manually. Allowing split rooms within one campaign to drift onto independent local clocks would break cross-room causality (switches opening doors, patrols, alarms) AND allow world-wide synchronous comms (`mental_link`, `resource_gated_artifact` *Sending*, `tuned_frequency` radio, `persistent_network`) to leak future messages into the past.

## Decision
Implement three coordinated Layer-0 extensions across `covert_ops.py`, `time_skip.py`, `vm.py`, `blocks.py`, and `mud_parser/social_dsl.py`:

1. **Full Persona Bundle Disguise Slots (`DisguisePreset`) & MUD Verbs**:
   - Add `DisguisePreset` (`EntityState.disguise_presets`) capturing `alias_id`, `presented_name`, `presented_tags`, `disguise_source`, optional `outfit_preset_id`, `required_item_ids`, `voice_disguised` / `voice_modulator_profile_id`, portrait/token overrides, `don_action_id`, and `don_duration_seconds`.
   - Extend `DisguisePillarConfig` with `default_don_duration_seconds`, `default_doff_duration_seconds`, and `source_don_durations_seconds` (remaining instant/`None` when omitted).
   - Add `save_disguise_preset`, `list_disguise_presets`, `delete_disguise_preset`, `resolve_disguise_don_duration`, and `don_disguise_preset` (applying disguise + linked `OutfitPreset` atomically when instant, or staging a background `ActiveTimedActivity` + optional `TimeSkipProposal` when a ruleset duration `> 0` applies).
   - Extend `mud_parser/social_dsl.py` with `COVERT_VERBS` (`hide`, `sneak`, `steal`, `plant`, `disguise`) and `TIME_VERBS` (`timeskip`, `wait`) routing deterministically to `"covert"` and `"time_control"` categories.

2. **Stealth Pillar Alignment Upgrades (`blocks.py`, `vm.py`, `covert_ops.py`)**:
   - Fix `resolve_awareness_level` (delegated by `get_awareness_level`) so unset `(observer, target)` pairs return `unaware_level` only while `target` retains at least one non-bypassed hidden condition, and `detected_level` otherwise.
   - Add `StealthPillarConfig.visible_levels` (defaulting to `(detected_level,)` when empty) and `StealthPillarConfig.sensory_bypass_tags` (mapping a `hidden_condition_id` to observer tags that negate it, dormant when empty).
   - Add `EntityState.stealth_score` (auto-updated when an action in `StealthPillarConfig.hide_action_ids` resolves a roll; editable via `set_stealth_score` / `STEALTH_SCORE_UPDATED`, surfaced cleanly in `ComputedEntityView` only when stealth is active) and inject `@awareness` (`self_sees_target`, `target_sees_self`, `self_visible_to_target`, `target_visible_to_self`) into action/hook AST contexts.

3. **Tightened Option 3 — Hybrid Synchronized Time Skips (`backend/app/ruleset_vm/time_skip.py`)**:
   - **Single Monotonic Campaign Clock + Non-Blocking Timed Activities**: Inside any single campaign/party (across rooms, cities, or star systems), `SceneState.elapsed_world_seconds` is strictly authoritative. Starting a timed action (`ActiveTimedActivity`, `start_timed_activity`) and opening a `TimeSkipProposal` (`propose_time_skip`) never blocks other rooms: other players can vote `"approve"`, `"hold_act_first"`, or `"keep_exploring"` (dismissing the table prompt while the background task ticks naturally as Group B acts — eliminating switch/door/patrol and world-wide synchronous comms causality paradoxes), or register a `ConcurrentActivitySelection` (`schedule_concurrent_activity`) to perform during the window.
   - **GM Authority & Interruptions**: `gm_trigger_time_skip` lets authorized `gm`/`co_gm`/`host` seats advance time directly or prompt players. `interrupt_time_skip` advances world time only up to `elapsed_before_interrupt`, pauses remaining interruptible `ActiveTimedActivity` entries with preserved progress, and fires `on_time_skip_interrupted` / `on_timed_activity_interrupted`.
   - **Cross-Branch CoW Isolation Boundary**: Independent timelines exist only between separate multi-party Copy-on-Write expeditions (Phase 14 `guild-server`), where `resolve_cross_branch_comm_delivery_mode()` routes cross-branch comms to `queue_until_settlement` rather than live synchronous delivery.

## Consequences
### Positive
- Disguises compose registered outfits, required props, voice modulation, portrait/token overrides, and ruleset donning durations under one event-sourced preset lifecycle.
- Stealth rulesets can express cached stealth DCs (`@target.stealth_score`), awareness-gated strikes (`@awareness.*`), multi-tier visibility, and sensory bypass tags purely declaratively.
- Split-party rooms never block one another and never violate switch/door, patrol, or world-wide synchronous comms causality.

### Negative / Trade-offs
- Adds `schemas/disguise_preset.schema.json` and `schemas/time_skip.schema.json`, plus 5 new `VmEventType` variants (`STEALTH_SCORE_UPDATED`, `DISGUISE_PRESET_UPDATED`, `TIMED_ACTIVITY_UPDATED`, `TIME_SKIP_UPDATED`, `WORLD_TIME_ADVANCED`).

### Neutral
- Registers `TIME_SKIP_MODULE_MANIFEST` (`module_id="synchronized_time_skip"`, `spec_section="1.5.7"`).

## Compliance & Verification
- Verified by `backend/tests/unit/test_covert_ops.py`, `backend/tests/unit/test_time_skip.py`, `backend/tests/unit/test_mud_parser.py`, `backend/tests/property/test_covert_ops_properties.py`, `backend/tests/property/test_time_skip_properties.py`, `tools/generate_types.py --check`, `tools/lint_agnosticism.py`, `tools/lint_modularity.py`, `pyright`, and `pytest -m zero_ai`.
