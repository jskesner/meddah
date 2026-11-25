# 0134. Universal Ruleset-Interpreting Covert Operations (Stealth, Theft & Disguises)

- **Date**: 2026-11-25
- **Status**: Accepted
- **Deciders**: User, Antigravity Agent
- **Related Issues / Decisions**: Golden Rule #1 (`ADR-0128`), Golden Rule #4 (`ADR-0131`), `ADR-0002`, `ADR-0039`, `ADR-0133`, Volume 1 §1.1.4B (`docs/design/tech_spec_01_core_vm_and_ingestion.md`), Volume 3 §1.21 (`docs/design/tech_spec_03_world_cosmology_and_society.md`), Volume 5 §1.16 (`docs/design/tech_spec_05_gameplay_systems_and_anatomy.md`)

## Context & Problem Statement
Tabletop and narrative RPGs vary dramatically in how they resolve stealth, pickpocketing/evidence planting, and disguises—ranging from binary hidden conditions and passive perception thresholds to multi-stage alert meters, faction heat, social deception checks, or completely rules-light fiction where covert mechanics do not exist. Hardcoding stealth rolls, sneak-attack math, perception DCs, automatic condition removal, or universal theft rules inside Meddah would violate Golden Rule #1 (`ADR-0128`) and Golden Rule #4 (`ADR-0131`), and would override established mechanics already declared by the active ruleset.

Conversely, leaving covert operations out of Layer-0 forces later subsystems (Layer-1 MUD command parser, Layer-2 campaign memory & witness engines, P5 multiplayer fog-of-war/comms filtering, P6 VTT/sheet UI, P8 law & crime, and P9 commerce/fencing) to reinvent ad-hoc state outside deterministic `VmEvent` replay and `state_hash()` verification.

## Decision
Introduce a dormant-by-default, purely **ruleset-interpreting** Covert Operations primitive layer (`CovertOpsConfigBlock` in `backend/app/ruleset_vm/blocks.py` and `backend/app/ruleset_vm/covert_ops.py`) paired with additive Layer-0 VM state (`SceneState`, `EntityState`, `ItemNode`):

1. **Granular 3-Pillar Binding (`CovertOpsConfigBlock`) — Interpret, Never Override**:
   - Rulesets optionally declare `RulesetSchema.covert_ops` containing three independent pillar configurations: `stealth: StealthPillarConfig | None`, `theft: TheftPillarConfig | None`, and `disguise: DisguisePillarConfig | None`.
   - Any omitted pillar remains completely dormant (`ADR-0131`): calling a dormant pillar's transition helper raises `PermissionError`, and rulesets without `covert_ops` experience zero behavioral change.
   - Bindings reference existing ruleset `ActionBlock`, `ConditionBlock`, and `EventHookBlock` IDs rather than introducing competing mechanics. In particular, `StealthPillarConfig.sync_hidden_condition_on_detect` defaults to `False` so per-observer awareness transitions never automatically strip or override ruleset-defined hidden conditions unless the ruleset explicitly opts into synchronization.

2. **Stealth Pillar — Per-Observer Awareness Map & Noise Hooks (`SceneState.awareness_map`)**:
   - Tracks sparse per-observer awareness states (`awareness_map[observer_id][target_id]`) validated against the ruleset's `StealthPillarConfig.awareness_levels`.
   - Provides pure observer queries (`get_awareness_level`, `is_target_visible_to_observer`) and audited event transitions (`AWARENESS_CHANGED` via `set_awareness_level` or declarative `EffectSpec(kind="set_awareness")`), plus `on_awareness_changed` and `on_stealth_noise` ECA hooks (triggered automatically on actions carrying `StealthPillarConfig.noisy_action_tags` and via `notify_stealth_noise`).

3. **Theft Pillar — Item Provenance, Slot Accessibility, Transfers & Delayed Discovery (`inventory_graph.py`, `vm.py`)**:
   - Extends `ItemNode` with `owner_entity_id`, `origin_jurisdiction_id`, `stolen_from_entity_id`, `provenance_state` (`"legitimate" | "stolen" | "planted" | "contraband"`), and `slot_accessibility` (`"open" | "pouched" | "worn_secure" | "concealed"`), exposed via `item_eval_context()` for ruleset AST conditions/formulas.
   - Provides atomic subtree-preserving cross-inventory transfers (`transfer_item_between_graphs`, `transfer_scene_item`, `ITEM_TRANSFERRED`, `EffectSpec(kind="transfer_item")`), provenance tagging/laundering (`mark_scene_item_provenance`, `ITEM_PROVENANCE_CHANGED`, `EffectSpec(kind="mark_provenance")`), and deterministic delayed theft discovery (`PendingMissingItemNotice`, `tick_missing_item_notices`, `MISSING_NOTICE_TICKED`) firing `on_item_stolen`, `on_item_planted`, and `on_missing_item_noticed`.

4. **Disguise Pillar — Dedicated Persona Overlay Composing Apparel & Forms (`ActiveDisguiseState`)**:
   - Adds `EntityState.active_disguise: ActiveDisguiseState | None` (`alias_id`, `presented_name`, `presented_tags`, `disguise_source`, `quality_score`, `voice_disguised`, `portrait_override_ref`, `token_override_ref`, `seen_through_by`).
   - Strictly non-stat: leaves `base_properties`, pools, and active transformations untouched while composing via `resolve_perceived_identity()` with `inventory_graph.compute_visible_appearance()` apparel/concealment and `FormBlock` portrait/token overrides.
   - Emits `DISGUISE_CHANGED` (`apply`, `seen_through`, `blow`), `on_disguise_applied`, `on_disguise_scrutinized` (including unmodulated speech scrutiny via `check_speech_disguise_scrutiny`), and `on_disguise_blown`, plus declarative `apply_disguise` and `reveal_disguise` effects.

5. **Host-Configurable PvP Covert Policy (`SceneState.pvp_covert_policy`)**:
   - Enforces `pvp_covert_policy: "npc_only" | "gm_approved" | "unrestricted"` (default `"npc_only"`) via `EntityState.is_player_controlled` and `COVERT_POLICY_UPDATED` (`set_pvp_covert_policy`), blocking unapproved player-to-player covert scrutiny, awareness sweeps, or pickpocket/plant actions at the VM layer unless GM-approved or explicitly configured.

## Consequences
### Positive
- Supports fantasy stealth/sleight-of-hand, heist/cyberpunk security & comm-bleed alerts, political masquerades, and rules-light zero-covert games cleanly without hardcoding game rules.
- Preserves exact deterministic `replay_events()` and `state_hash()` parity across all 6 new `VmEventType` variants and additive schema fields.
- Gives downstream phases (`P2` ingestion probes, `P2.5` CLI covert commands, `P5` FoW/comms gating, `P6` VTT/sheet badges, `P8` witnesses & alias bounties, `P9` fencing) a single authoritative Layer-0 contract.

### Negative / Trade-offs
- Adds `schemas/covert_ops.schema.json` and additive optional fields to `RulesetSchema`, `EntityState`, `SceneState`, `ItemNode`, `EffectSpec`, and `VmEventType`.

### Neutral
- Registered `COVERT_OPS_MODULE_MANIFEST` (`module_id="covert_ops"`, `spec_section="1.1.4B"`, `requires_any_primitive=("covert_stealth", "covert_theft", "covert_disguise")`) for opt-in/modular campaign toggling.

## Compliance & Verification
- Verified by `backend/tests/unit/test_covert_ops.py`, `backend/tests/property/test_covert_ops_properties.py`, `tools/generate_types.py --check`, `tools/lint_agnosticism.py`, `tools/lint_modularity.py`, `pyright` strict mode, and `pytest -m zero_ai`.
