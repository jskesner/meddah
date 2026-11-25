"""Unit tests for Universal Ruleset-Interpreting Covert Operations (ADR-0134)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.ruleset_vm import (
    COVERT_OPS_MODULE_MANIFEST,
    ActionBlock,
    ActiveCondition,
    ActiveDisguiseState,
    CapacityRule,
    ConditionBlock,
    CovertOpsConfigBlock,
    DisguisePillarConfig,
    DisguisePreset,
    EffectSpec,
    EntityState,
    EventHookBlock,
    FormBlock,
    InventoryGraphState,
    ItemNode,
    ModuleRegistry,
    OutcomeTier,
    PackageManifest,
    PropertyBlock,
    RandomizerSpec,
    ResolutionMechanicBlock,
    ResourcePoolBlock,
    RulesetSchema,
    StealthPillarConfig,
    TheftPillarConfig,
    VmEvent,
    WearableLayerSpec,
    active_covert_pillars,
    add_item,
    advance_world_time,
    apply_disguise,
    apply_event,
    blow_disguise,
    check_speech_disguise_scrutiny,
    compute_entity_view,
    delete_disguise_preset,
    don_disguise_preset,
    evaluate_formula,
    execute_action,
    get_awareness_level,
    initialize_scene_state,
    is_pillar_active,
    is_target_visible_to_observer,
    item_eval_context,
    list_disguise_presets,
    mark_disguise_seen_through,
    mark_scene_item_provenance,
    notify_stealth_noise,
    replay_events,
    resolve_awareness_level,
    resolve_perceived_identity,
    resolve_target_visibility,
    save_disguise_preset,
    save_outfit_preset,
    set_awareness_level,
    set_pvp_covert_policy,
    set_stealth_score,
    state_hash,
    tick_missing_item_notices,
    transfer_scene_item,
    wear_item,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
RULES_LIGHT_PATH = (
    REPO_ROOT / "sample_rulesets" / "conformance" / "rules_light_narrative" / "ruleset.json"
)


def _covert_ruleset(
    *,
    stealth: StealthPillarConfig | None = None,
    theft: TheftPillarConfig | None = None,
    disguise: DisguisePillarConfig | None = None,
    include_covert_block: bool = True,
) -> RulesetSchema:
    covert_block = (
        CovertOpsConfigBlock(stealth=stealth, theft=theft, disguise=disguise)
        if include_covert_block
        else None
    )
    hooks = {
        "hook_awareness": EventHookBlock(
            hook_id="hook_awareness",
            event_name="on_awareness_changed",
            effects=(
                EffectSpec(
                    kind="advance_clock",
                    target_scope="scene",
                    target_key="awareness_hooks",
                    formula="1",
                ),
            ),
        ),
        "hook_noise": EventHookBlock(
            hook_id="hook_noise",
            event_name="on_stealth_noise",
            effects=(
                EffectSpec(
                    kind="advance_clock",
                    target_scope="scene",
                    target_key="noise_hooks",
                    formula="1",
                ),
            ),
        ),
        "hook_stolen": EventHookBlock(
            hook_id="hook_stolen",
            event_name="on_item_stolen",
            effects=(
                EffectSpec(
                    kind="advance_clock",
                    target_scope="scene",
                    target_key="stolen_hooks",
                    formula="1",
                ),
            ),
        ),
        "hook_planted": EventHookBlock(
            hook_id="hook_planted",
            event_name="on_item_planted",
            effects=(
                EffectSpec(
                    kind="advance_clock",
                    target_scope="scene",
                    target_key="planted_hooks",
                    formula="1",
                ),
            ),
        ),
        "hook_missing": EventHookBlock(
            hook_id="hook_missing",
            event_name="on_missing_item_noticed",
            effects=(
                EffectSpec(
                    kind="advance_clock",
                    target_scope="scene",
                    target_key="missing_notice_hooks",
                    formula="1",
                ),
            ),
        ),
        "hook_disguise_applied": EventHookBlock(
            hook_id="hook_disguise_applied",
            event_name="on_disguise_applied",
            effects=(
                EffectSpec(
                    kind="advance_clock",
                    target_scope="scene",
                    target_key="disguise_applied_hooks",
                    formula="1",
                ),
            ),
        ),
        "hook_scrutiny": EventHookBlock(
            hook_id="hook_scrutiny",
            event_name="on_disguise_scrutinized",
            effects=(
                EffectSpec(
                    kind="advance_clock",
                    target_scope="scene",
                    target_key="scrutiny_hooks",
                    formula="1",
                ),
            ),
        ),
        "hook_blown": EventHookBlock(
            hook_id="hook_blown",
            event_name="on_disguise_blown",
            effects=(
                EffectSpec(
                    kind="advance_clock",
                    target_scope="scene",
                    target_key="blown_hooks",
                    formula="1",
                ),
            ),
        ),
    }

    return RulesetSchema(
        manifest=PackageManifest(
            package_type="ruleset",
            package_id="covert_test_ruleset",
            name="Covert Test Ruleset",
            version="0.1.0",
        ),
        properties={
            "guile": PropertyBlock(prop_id="guile", label="Guile", default_value=14),
            "vigilance": PropertyBlock(prop_id="vigilance", label="Vigilance", default_value=12),
            "derived_edge": PropertyBlock(
                prop_id="derived_edge",
                label="Derived Edge",
                formula="@self.guile + 2",
            ),
        },
        resource_pools={
            "stamina": ResourcePoolBlock(
                pool_id="stamina",
                label="Stamina",
                default_current=10,
                max_formula="20",
                min_value=0,
            ),
        },
        conditions={
            "concealed_in_shadow": ConditionBlock(
                condition_id="concealed_in_shadow",
                label="Concealed in Shadow",
                description="Ruleset-defined stealth posture.",
                property_modifiers={"guile": "2"},
            ),
            "masked": ConditionBlock(
                condition_id="masked",
                label="Masked",
                description="Ruleset-defined disguise state.",
            ),
        },
        resolutions={
            "disguise_craft_roll": ResolutionMechanicBlock(
                mech_id="disguise_craft_roll",
                label="Disguise Craft Roll",
                randomizer=RandomizerSpec(kind="none", base_value=17),
                tiers=(
                    OutcomeTier(
                        tier_id="crafted",
                        label="Crafted",
                        condition="true",
                        effects=(
                            EffectSpec(
                                kind="apply_disguise",
                                target_scope="self",
                                target_key="envoy_kestrel",
                                formula="Envoy Kestrel",
                            ),
                        ),
                    ),
                ),
            ),
        },
        actions={
            "blend_in": ActionBlock(
                action_id="blend_in",
                label="Blend In",
                category="action",
                default_effects=(
                    EffectSpec(
                        kind="add_condition",
                        target_scope="self",
                        target_key="concealed_in_shadow",
                    ),
                ),
            ),
            "spot_intruder": ActionBlock(
                action_id="spot_intruder",
                label="Spot Intruder",
                category="action",
                requires_target=True,
                default_effects=(
                    EffectSpec(
                        kind="set_awareness",
                        target_scope="target",
                        target_key="suspected",
                    ),
                ),
            ),
            "loud_strike": ActionBlock(
                action_id="loud_strike",
                label="Loud Strike",
                category="action",
                tags=("loud",),
                default_effects=(
                    EffectSpec(
                        kind="advance_clock",
                        target_scope="scene",
                        target_key="strikes",
                        formula="1",
                    ),
                ),
            ),
            "pickpocket": ActionBlock(
                action_id="pickpocket",
                label="Pickpocket",
                category="action",
                requires_target=True,
                default_effects=(
                    EffectSpec(
                        kind="transfer_item",
                        target_scope="target",
                        target_key="ruby_seal",
                        formula="stolen",
                        duration_turns=2,
                    ),
                ),
            ),
            "plant_contraband": ActionBlock(
                action_id="plant_contraband",
                label="Plant Item",
                category="action",
                requires_target=True,
                default_effects=(
                    EffectSpec(
                        kind="transfer_item",
                        target_scope="self",
                        target_key="forged_note",
                        formula="planted",
                    ),
                ),
            ),
            "launder_item": ActionBlock(
                action_id="launder_item",
                label="Launder Item",
                category="action",
                default_effects=(
                    EffectSpec(
                        kind="mark_provenance",
                        target_scope="self",
                        target_key="ruby_seal",
                        formula="legitimate",
                    ),
                ),
            ),
            "craft_disguise": ActionBlock(
                action_id="craft_disguise",
                label="Craft Disguise",
                category="action",
                resolution_id="disguise_craft_roll",
            ),
            "scrutinize_disguise": ActionBlock(
                action_id="scrutinize_disguise",
                label="Scrutinize Disguise",
                category="action",
                requires_target=True,
                default_effects=(
                    EffectSpec(
                        kind="reveal_disguise",
                        target_scope="target",
                        target_key="",
                        forced=False,
                    ),
                ),
            ),
            "rip_off_mask": ActionBlock(
                action_id="rip_off_mask",
                label="Rip Off Mask",
                category="action",
                requires_target=True,
                default_effects=(
                    EffectSpec(
                        kind="reveal_disguise",
                        target_scope="target",
                        target_key="",
                        forced=True,
                    ),
                ),
            ),
        },
        forms={
            "shadow_mantle": FormBlock(
                form_id="shadow_mantle",
                label="Shadow Mantle",
                property_mode="delta_overlay",
                property_values={"guile": 1},
                portrait_override_ref="form_portrait.png",
                token_override_ref="form_token.png",
            ),
        },
        event_hooks=hooks,
        covert_ops=covert_block,
    )


def _full_covert_ruleset(
    *,
    sync_hidden_condition_on_detect: bool = False,
    requires_voice_modulation_for_speech: bool = False,
    default_notice_delay_turns: int | None = 2,
) -> RulesetSchema:
    return _covert_ruleset(
        stealth=StealthPillarConfig(
            hide_action_ids=("blend_in",),
            hidden_condition_ids=("concealed_in_shadow",),
            detection_action_ids=("spot_intruder",),
            sync_hidden_condition_on_detect=sync_hidden_condition_on_detect,
            noisy_action_tags=("loud",),
        ),
        theft=TheftPillarConfig(
            steal_action_ids=("pickpocket",),
            plant_action_ids=("plant_contraband",),
            default_notice_delay_turns=default_notice_delay_turns,
        ),
        disguise=DisguisePillarConfig(
            disguise_action_ids=("craft_disguise",),
            scrutiny_action_ids=("scrutinize_disguise",),
            disguised_condition_ids=("masked",),
            requires_voice_modulation_for_speech=requires_voice_modulation_for_speech,
        ),
    )


@pytest.mark.zero_ai
def test_dormancy_on_rules_light_fixture_and_module_registry_round_trip() -> None:
    """Rulesets without covert_ops leave all 3 covert pillars completely dormant."""
    raw = json.loads(RULES_LIGHT_PATH.read_text(encoding="utf-8"))
    rules_light = RulesetSchema.model_validate(raw)

    assert rules_light.covert_ops is None
    assert active_covert_pillars(rules_light) == ()
    assert not is_pillar_active(rules_light, "stealth")
    assert not is_pillar_active(rules_light, "theft")
    assert not is_pillar_active(rules_light, "disguise")

    actor = EntityState(
        entity_id="pc_1",
        name="Vera",
        active_disguise=ActiveDisguiseState(
            alias_id="shadow_alias",
            presented_name="Masked Stranger",
        ),
    )
    npc = EntityState(entity_id="npc_1", name="Watcher")
    inv_a = add_item(
        InventoryGraphState(),
        ItemNode(item_id="token_1", template_id="token", name="Signet Token"),
    )
    scene = initialize_scene_state(
        rules_light,
        "dormant_scene",
        [actor, npc],
        entity_inventories={"npc_1": inv_a, "pc_1": InventoryGraphState()},
    )

    assert is_target_visible_to_observer(rules_light, scene, "npc_1", "pc_1") is True

    # Dormant disguise pillar never leaks ActiveDisguiseState into views or perceived identity
    view = compute_entity_view(rules_light, scene.entities["pc_1"])
    assert view.active_disguise_alias is None
    assert view.presented_name == "Vera"
    assert view.disguise_quality is None
    perceived = resolve_perceived_identity(rules_light, scene, "pc_1", observer_id="npc_1")
    assert perceived.is_disguised is False
    assert perceived.perceived_name == "Vera"
    assert perceived.perceived_alias_id is None

    with pytest.raises(PermissionError, match="dormant"):
        set_awareness_level(rules_light, scene, "npc_1", "pc_1", "detected")
    with pytest.raises(PermissionError, match="dormant"):
        transfer_scene_item(rules_light, scene, "npc_1", "pc_1", "token_1")
    with pytest.raises(PermissionError, match="dormant"):
        apply_disguise(rules_light, scene, "pc_1", "alias_a", "Fake Vera")

    # ModuleRegistry dormancy + MODULE_OVERRIDE toggle replay invariance
    reg = ModuleRegistry()
    reg.register(COVERT_OPS_MODULE_MANIFEST)
    assert reg.resolve_status("covert_ops", ()).state == "dormant"
    assert reg.resolve_status("covert_ops", ("covert_stealth",)).state == "available"
    reg.set_enabled("covert_ops", True)
    assert reg.resolve_status("covert_ops", ("covert_stealth",)).state == "active"

    off_evt = VmEvent(
        event_id="evt_mod_off",
        event_type="MODULE_OVERRIDE",
        actor_id="host",
        payload={"module_id": "covert_ops", "enabled": False},
    )
    on_evt = VmEvent(
        event_id="evt_mod_on",
        event_type="MODULE_OVERRIDE",
        actor_id="host",
        payload={"module_id": "covert_ops", "enabled": True},
    )
    scene_active = initialize_scene_state(
        rules_light,
        "dormant_mod",
        [actor, npc],
        active_modules=("covert_ops",),
    )
    s1 = apply_event(rules_light, scene_active, off_evt)
    assert s1.active_modules == ()
    s2 = apply_event(rules_light, s1, on_evt)
    assert s2.active_modules == ("covert_ops",)
    replayed = replay_events(rules_light, scene_active, [off_evt, on_evt])
    assert state_hash(replayed) == state_hash(s2)


@pytest.mark.zero_ai
def test_granular_stealth_only_ruleset_keeps_theft_and_disguise_dormant() -> None:
    """Declaring only StealthPillarConfig activates stealth while blocking theft and disguise."""
    rs = _covert_ruleset(
        stealth=StealthPillarConfig(hidden_condition_ids=("concealed_in_shadow",)),
        theft=None,
        disguise=None,
    )
    assert active_covert_pillars(rs) == ("stealth",)
    assert is_pillar_active(rs, "stealth") is True
    assert is_pillar_active(rs, "theft") is False
    assert is_pillar_active(rs, "disguise") is False

    rogue = EntityState(entity_id="pc_1", name="Rogue", is_player_controlled=True)
    guard = EntityState(entity_id="npc_1", name="Guard")
    guard_inv = add_item(
        InventoryGraphState(),
        ItemNode(item_id="key_1", template_id="key", name="Gate Key"),
    )
    scene = initialize_scene_state(
        rs,
        "stealth_only",
        [rogue, guard],
        entity_inventories={"npc_1": guard_inv, "pc_1": InventoryGraphState()},
    )

    res = set_awareness_level(rs, scene, "npc_1", "pc_1", "suspected")
    assert get_awareness_level(rs, res.state, "npc_1", "pc_1") == "suspected"

    with pytest.raises(PermissionError, match="theft"):
        transfer_scene_item(rs, res.state, "npc_1", "pc_1", "key_1")
    with pytest.raises(PermissionError, match="disguise"):
        apply_disguise(rs, res.state, "pc_1", "guard_coat", "Guard")


@pytest.mark.zero_ai
def test_stealth_awareness_respects_ruleset_hidden_conditions_unless_opted_in() -> None:
    """Awareness transitions interpret ruleset conditions cleanly without auto-overriding."""
    rs_preserve = _full_covert_ruleset(sync_hidden_condition_on_detect=False)
    rogue = EntityState(
        entity_id="pc_1",
        name="Rogue",
        is_player_controlled=True,
        conditions={"concealed_in_shadow": ActiveCondition(condition_id="concealed_in_shadow")},
    )
    guard_1 = EntityState(entity_id="npc_1", name="Watchman A")
    guard_2 = EntityState(entity_id="npc_2", name="Watchman B")
    scene = initialize_scene_state(rs_preserve, "stealth_sync", [rogue, guard_1, guard_2])

    assert is_target_visible_to_observer(rs_preserve, scene, "npc_1", "pc_1") is False
    assert is_target_visible_to_observer(rs_preserve, scene, "npc_2", "pc_1") is False

    detected = set_awareness_level(rs_preserve, scene, "npc_1", "pc_1", "detected")
    assert detected.awareness_level == "detected"
    assert get_awareness_level(rs_preserve, detected.state, "npc_1", "pc_1") == "detected"
    assert is_target_visible_to_observer(rs_preserve, detected.state, "npc_1", "pc_1") is True
    assert is_target_visible_to_observer(rs_preserve, detected.state, "npc_2", "pc_1") is False
    assert "concealed_in_shadow" in detected.state.entities["pc_1"].conditions
    assert detected.state.clocks["awareness_hooks"] == 1
    assert [e.event_type for e in detected.events] == ["AWARENESS_CHANGED", "CLOCK_ADVANCED"]

    # Explicit opt-in removes ruleset hidden condition when detected
    rs_sync = _full_covert_ruleset(sync_hidden_condition_on_detect=True)
    detected_sync = set_awareness_level(rs_sync, scene, "npc_1", "pc_1", "detected")
    assert "concealed_in_shadow" not in detected_sync.state.entities["pc_1"].conditions
    assert [e.event_type for e in detected_sync.events] == [
        "AWARENESS_CHANGED",
        "CONDITION_CHANGED",
        "CLOCK_ADVANCED",
    ]


@pytest.mark.zero_ai
def test_stealth_noise_and_declarative_set_awareness_effect() -> None:
    """Noisy actions/comms bleed trigger on_stealth_noise; set_awareness updates awareness."""
    rs = _full_covert_ruleset()
    rogue = EntityState(
        entity_id="pc_1",
        name="Rogue",
        is_player_controlled=True,
        conditions={"concealed_in_shadow": ActiveCondition(condition_id="concealed_in_shadow")},
    )
    guard = EntityState(entity_id="npc_1", name="Sentry")
    scene = initialize_scene_state(rs, "noise_scene", [rogue, guard])

    res_loud = execute_action(rs, scene, "pc_1", "loud_strike")
    assert res_loud.state.clocks["strikes"] == 1
    assert res_loud.state.clocks["noise_hooks"] == 1

    res_comms = notify_stealth_noise(
        rs,
        res_loud.state,
        "pc_1",
        source="comms_bleed",
        detail="unsealed_helmet",
    )
    assert res_comms.state.clocks["noise_hooks"] == 2

    res_spot = execute_action(rs, res_comms.state, "npc_1", "spot_intruder", target_id="pc_1")
    assert get_awareness_level(rs, res_spot.state, "npc_1", "pc_1") == "suspected"
    assert res_spot.state.clocks["awareness_hooks"] == 1

    all_events = [*res_loud.events, *res_comms.events, *res_spot.events]
    assert state_hash(replay_events(rs, scene, all_events)) == state_hash(res_spot.state)


@pytest.mark.zero_ai
def test_theft_provenance_subtree_transfer_and_delayed_missing_notice() -> None:
    """Stealing preserves container subtrees, updates provenance, and ticks delayed notice."""
    rs = _full_covert_ruleset(default_notice_delay_turns=2)
    thief = EntityState(entity_id="pc_1", name="Pickpocket", is_player_controlled=True)
    noble = EntityState(entity_id="npc_1", name="Lord Vance")

    pouch = ItemNode(
        item_id="velvet_pouch",
        template_id="pouch",
        name="Velvet Pouch",
        unit_weight=0.5,
        slot_accessibility="pouched",
        owner_entity_id="npc_1",
        origin_jurisdiction_id="high_ward",
        container_capacity=CapacityRule(mode="slots", max_slots=4),
    )
    seal = ItemNode(
        item_id="ruby_seal",
        template_id="seal",
        name="Ruby Seal",
        unit_weight=0.2,
        slot_accessibility="worn_secure",
        concealable=True,
        owner_entity_id="npc_1",
        origin_jurisdiction_id="high_ward",
        tags=("signet",),
    )

    seal_ctx = item_eval_context(seal)
    assert seal_ctx["slot_accessibility"] == "worn_secure"
    assert seal_ctx["provenance_state"] == "legitimate"
    assert seal_ctx["owner_entity_id"] == "npc_1"
    assert seal_ctx["origin_jurisdiction_id"] == "high_ward"
    assert evaluate_formula("slot_accessibility == 'worn_secure'", seal_ctx) is True
    assert evaluate_formula("provenance_state == 'stolen'", seal_ctx) is False

    victim_inv = InventoryGraphState()
    victim_inv = add_item(victim_inv, pouch)
    victim_inv = add_item(victim_inv, seal, container_id="velvet_pouch")
    thief_inv = InventoryGraphState()

    scene = initialize_scene_state(
        rs,
        "heist_scene",
        [thief, noble],
        entity_inventories={"npc_1": victim_inv, "pc_1": thief_inv},
    )

    with pytest.raises(ValueError, match="differ"):
        transfer_scene_item(rs, scene, "npc_1", "npc_1", "velvet_pouch")

    steal_res = transfer_scene_item(rs, scene, "npc_1", "pc_1", "velvet_pouch")
    s1 = steal_res.state
    assert steal_res.transferred_item_id == "velvet_pouch"
    assert "velvet_pouch" not in s1.entity_inventories["npc_1"].items
    assert "ruby_seal" not in s1.entity_inventories["npc_1"].items
    thief_after = s1.entity_inventories["pc_1"]
    assert "velvet_pouch" in thief_after.items
    assert "ruby_seal" in thief_after.items
    assert thief_after.parent_container["ruby_seal"] == "velvet_pouch"
    assert thief_after.items["ruby_seal"].provenance_state == "stolen"
    assert thief_after.items["ruby_seal"].stolen_from_entity_id == "npc_1"
    assert "stolen" in thief_after.items["ruby_seal"].tags
    assert s1.clocks["stolen_hooks"] == 1
    assert len(s1.pending_missing_notices) == 1
    assert s1.pending_missing_notices[0].remaining_turns == 2

    tick1 = tick_missing_item_notices(rs, s1, turns=1)
    assert tick1.triggered_notices == ()
    assert len(tick1.state.pending_missing_notices) == 1
    assert tick1.state.pending_missing_notices[0].remaining_turns == 1
    assert tick1.state.clocks.get("missing_notice_hooks", 0) == 0

    tick2 = tick_missing_item_notices(rs, tick1.state, turns=1)
    assert len(tick2.triggered_notices) == 1
    assert tick2.triggered_notices[0].item_id == "velvet_pouch"
    assert tick2.state.pending_missing_notices == ()
    assert tick2.state.clocks["missing_notice_hooks"] == 1

    all_events = [*steal_res.events, *tick1.events, *tick2.events]
    assert state_hash(replay_events(rs, scene, all_events)) == state_hash(tick2.state)


@pytest.mark.zero_ai
def test_plant_launder_and_declarative_theft_effects() -> None:
    """Planting, fencing/laundering, and declarative theft EffectSpecs work deterministically."""
    rs = _full_covert_ruleset()
    rogue = EntityState(entity_id="pc_1", name="Operative", is_player_controlled=True)
    mark = EntityState(entity_id="npc_1", name="Magistrate")

    rogue_inv = add_item(
        InventoryGraphState(),
        ItemNode(item_id="forged_note", template_id="note", name="Forged Ledger"),
    )
    mark_inv = add_item(
        InventoryGraphState(),
        ItemNode(item_id="ruby_seal", template_id="seal", name="Ruby Seal"),
    )
    scene = initialize_scene_state(
        rs,
        "plant_scene",
        [rogue, mark],
        entity_inventories={"pc_1": rogue_inv, "npc_1": mark_inv},
    )

    # Plant directly
    plant_res = transfer_scene_item(
        rs,
        scene,
        "pc_1",
        "npc_1",
        "forged_note",
        provenance_state="planted",
    )
    planted_item = plant_res.state.entity_inventories["npc_1"].items["forged_note"]
    assert planted_item.provenance_state == "planted"
    assert "planted" in planted_item.tags
    assert plant_res.state.clocks["planted_hooks"] == 1
    assert plant_res.state.pending_missing_notices == ()

    # Declarative steal & launder actions
    pick_res = execute_action(rs, plant_res.state, "pc_1", "pickpocket", target_id="npc_1")
    stolen_seal = pick_res.state.entity_inventories["pc_1"].items["ruby_seal"]
    assert stolen_seal.provenance_state == "stolen"
    assert stolen_seal.stolen_from_entity_id == "npc_1"
    assert pick_res.state.clocks["stolen_hooks"] == 1
    assert len(pick_res.state.pending_missing_notices) == 1

    launder_res = execute_action(rs, pick_res.state, "pc_1", "launder_item")
    clean_seal = launder_res.state.entity_inventories["pc_1"].items["ruby_seal"]
    assert clean_seal.provenance_state == "legitimate"
    assert clean_seal.stolen_from_entity_id is None
    assert "stolen" not in clean_seal.tags

    # Direct mark_scene_item_provenance on planted evidence -> contraband
    contra_res = mark_scene_item_provenance(
        rs,
        launder_res.state,
        "npc_1",
        "forged_note",
        "contraband",
        origin_jurisdiction_id="citadel",
    )
    flagged = contra_res.state.entity_inventories["npc_1"].items["forged_note"]
    assert flagged.provenance_state == "contraband"
    assert flagged.origin_jurisdiction_id == "citadel"
    assert "contraband" in flagged.tags

    all_events = [*plant_res.events, *pick_res.events, *launder_res.events, *contra_res.events]
    assert state_hash(replay_events(rs, scene, all_events)) == state_hash(contra_res.state)


@pytest.mark.zero_ai
def test_disguise_overlay_composes_apparel_and_forms_without_mutating_stats() -> None:
    """Disguises remain non-stat persona overlays composing apparel layers and active forms."""
    rs = _full_covert_ruleset()
    spy = EntityState(
        entity_id="pc_1",
        name="Elena",
        is_player_controlled=True,
        base_properties={"guile": 14, "vigilance": 12},
        pools={"stamina": 10},
        available_forms=("shadow_mantle",),
    )
    guard_a = EntityState(entity_id="npc_1", name="Gate Captain")
    guard_b = EntityState(entity_id="npc_2", name="Post Sentry")

    inv = InventoryGraphState()
    tunic = ItemNode(
        item_id="mail_shirt",
        template_id="mail",
        name="Chain Shirt",
        wearable=WearableLayerSpec(
            layer_id="protective_armor",
            covered_locations=("torso",),
            appearance_tags=("armored",),
        ),
    )
    cloak = ItemNode(
        item_id="velvet_cloak",
        template_id="cloak",
        name="Crimson Cloak",
        wearable=WearableLayerSpec(
            layer_id="outer_garment",
            covered_locations=("torso",),
            conceals_inner_layers=True,
            appearance_tags=("velvet_cloak",),
        ),
    )
    inv = add_item(inv, tunic)
    inv = wear_item(inv, "mail_shirt")
    inv = add_item(inv, cloak)
    inv = wear_item(inv, "velvet_cloak")

    scene = initialize_scene_state(
        rs,
        "masquerade",
        [spy, guard_a, guard_b],
        entity_inventories={"pc_1": inv},
    )

    # Shift form first so form portrait/token overrides exist underneath disguise
    form_evt = VmEvent(
        event_id="evt_form_1",
        event_type="FORM_CHANGED",
        actor_id="pc_1",
        payload={
            "entity_id": "pc_1",
            "op": "shift",
            "active_form": {
                "form_id": "shadow_mantle",
                "remaining_turns": None,
                "form_pools": {},
                "form_pool_maxes": {},
                "gear_handling": "merge_into_form",
                "previous_form_id": None,
                "involuntary": False,
                "source_entity_id": None,
            },
        },
    )
    scene_shifted = apply_event(rs, scene, form_evt)
    view_before = compute_entity_view(rs, scene_shifted.entities["pc_1"])

    disguise_res = apply_disguise(
        rs,
        scene_shifted,
        "pc_1",
        "lady_solenne",
        "Lady Solenne",
        presented_tags=("diplomat",),
        disguise_source="kit",
        quality_score=18,
        portrait_override_ref="disguise_portrait.png",
    )
    spy_after = disguise_res.state.entities["pc_1"]
    assert spy_after.base_properties == {"guile": 14, "vigilance": 12}
    assert spy_after.pools == {"stamina": 10}
    view_after = compute_entity_view(rs, spy_after)
    assert view_after.properties == view_before.properties
    assert view_after.active_disguise_alias == "lady_solenne"
    assert view_after.presented_name == "Lady Solenne"
    assert view_after.disguise_quality == 18
    assert disguise_res.state.clocks["disguise_applied_hooks"] == 1

    # Observer sees disguise name + portrait, form token fallback, and apparel + alias tags
    view_guard_a = resolve_perceived_identity(rs, disguise_res.state, "pc_1", observer_id="npc_1")
    assert view_guard_a.perceived_name == "Lady Solenne"
    assert view_guard_a.perceived_alias_id == "lady_solenne"
    assert view_guard_a.is_disguised is True
    assert view_guard_a.seen_through is False
    assert view_guard_a.portrait_override_ref == "disguise_portrait.png"
    assert view_guard_a.token_override_ref == "form_token.png"
    assert "diplomat" in view_guard_a.presented_tags
    assert "velvet_cloak" in view_guard_a.presented_tags
    assert "mail_shirt" in view_guard_a.concealed_item_ids

    # Guard A sees through disguise; Guard B stays fooled
    scrutiny_res = mark_disguise_seen_through(rs, disguise_res.state, "npc_1", "pc_1")
    assert scrutiny_res.state.clocks["scrutiny_hooks"] == 1
    seen_a = resolve_perceived_identity(rs, scrutiny_res.state, "pc_1", observer_id="npc_1")
    seen_b = resolve_perceived_identity(rs, scrutiny_res.state, "pc_1", observer_id="npc_2")
    assert seen_a.seen_through is True
    assert seen_a.perceived_name == "Elena"
    assert seen_a.perceived_alias_id is None
    assert seen_a.portrait_override_ref == "form_portrait.png"
    assert "diplomat" not in seen_a.presented_tags
    assert "velvet_cloak" in seen_a.presented_tags
    assert seen_b.seen_through is False
    assert seen_b.perceived_name == "Lady Solenne"

    blow_res = blow_disguise(rs, scrutiny_res.state, "pc_1", revealed_by_id="npc_1")
    assert blow_res.active_disguise is None
    assert blow_res.state.clocks["blown_hooks"] == 1

    all_events = [form_evt, *disguise_res.events, *scrutiny_res.events, *blow_res.events]
    assert state_hash(replay_events(rs, scene, all_events)) == state_hash(blow_res.state)


@pytest.mark.zero_ai
def test_disguise_speech_scrutiny_and_declarative_disguise_effects() -> None:
    """Speech without voice modulation triggers scrutiny; declarative disguise effects work."""
    rs = _full_covert_ruleset(requires_voice_modulation_for_speech=True)
    spy = EntityState(entity_id="pc_1", name="Spy", is_player_controlled=True)
    guard_1 = EntityState(entity_id="npc_1", name="Guard 1")
    guard_2 = EntityState(entity_id="npc_2", name="Guard 2")
    scene = initialize_scene_state(rs, "speech_scene", [spy, guard_1, guard_2])

    # Declarative craft_disguise uses resolution randomizer total (17)
    craft_res = execute_action(rs, scene, "pc_1", "craft_disguise")
    disguise = craft_res.state.entities["pc_1"].active_disguise
    assert disguise is not None
    assert disguise.alias_id == "envoy_kestrel"
    assert disguise.presented_name == "Envoy Kestrel"
    assert disguise.quality_score == 17

    # Modulated speech emits zero scrutiny events
    mod_res = check_speech_disguise_scrutiny(
        rs,
        craft_res.state,
        "pc_1",
        ("npc_1", "npc_2"),
        voice_modulated=True,
    )
    assert mod_res.events == ()

    # Unmodulated speech triggers on_disguise_scrutinized once per NPC observer
    unmod_res = check_speech_disguise_scrutiny(
        rs,
        craft_res.state,
        "pc_1",
        ("npc_1", "npc_2"),
        voice_modulated=False,
    )
    assert unmod_res.state.clocks["scrutiny_hooks"] == 2

    # Declarative reveal_disguise (scrutiny + forced blow)
    scrut_act = execute_action(
        rs, unmod_res.state, "npc_1", "scrutinize_disguise", target_id="pc_1"
    )
    after_scrut = scrut_act.state.entities["pc_1"].active_disguise
    assert after_scrut is not None
    assert "npc_1" in after_scrut.seen_through_by

    blow_act = execute_action(rs, scrut_act.state, "npc_1", "rip_off_mask", target_id="pc_1")
    assert blow_act.state.entities["pc_1"].active_disguise is None
    assert blow_act.state.clocks["blown_hooks"] == 1


@pytest.mark.zero_ai
def test_pvp_covert_policy_gating_and_declarative_skip() -> None:
    """Host pvp_covert_policy enforces npc_only, gm_approved, and unrestricted gates."""
    rs = _full_covert_ruleset()
    pc_1 = EntityState(entity_id="pc_1", name="PC One", is_player_controlled=True)
    pc_2 = EntityState(entity_id="pc_2", name="PC Two", is_player_controlled=True)
    npc_1 = EntityState(entity_id="npc_1", name="NPC Guard", is_player_controlled=False)

    inv_pc2 = add_item(
        InventoryGraphState(),
        ItemNode(item_id="ruby_seal", template_id="seal", name="PC Seal"),
    )
    scene = initialize_scene_state(
        rs,
        "pvp_scene",
        [pc_1, pc_2, npc_1],
        entity_inventories={"pc_1": InventoryGraphState(), "pc_2": inv_pc2},
    )
    assert scene.pvp_covert_policy == "npc_only"

    # Put disguise on pc_2 to test scrutiny gating
    d_res = apply_disguise(rs, scene, "pc_2", "merchant", "Traveling Merchant")
    s0 = d_res.state

    # Default npc_only blocks PC->PC across awareness, theft, scrutiny & declarative effects
    with pytest.raises(PermissionError, match="npc_only"):
        set_awareness_level(rs, s0, "pc_1", "pc_2", "detected")
    with pytest.raises(PermissionError, match="npc_only"):
        transfer_scene_item(rs, s0, "pc_2", "pc_1", "ruby_seal")
    with pytest.raises(PermissionError, match="npc_only"):
        mark_disguise_seen_through(rs, s0, "pc_1", "pc_2")

    # Declarative actions also skip PC->PC covert mutations under npc_only
    dec_pick = execute_action(rs, s0, "pc_1", "pickpocket", target_id="pc_2")
    assert "ruby_seal" in dec_pick.state.entity_inventories["pc_2"].items
    dec_scrut = execute_action(rs, dec_pick.state, "pc_1", "scrutinize_disguise", target_id="pc_2")
    assert dec_scrut.state.entities["pc_2"].active_disguise is not None
    assert dec_scrut.state.entities["pc_2"].active_disguise.seen_through_by == ()

    # PC<->NPC remains allowed under npc_only
    npc_ok = set_awareness_level(rs, dec_scrut.state, "pc_1", "npc_1", "suspected")
    assert get_awareness_level(rs, npc_ok.state, "pc_1", "npc_1") == "suspected"

    # Switch to gm_approved: blocked unless gm_approved=True
    pol_gm = set_pvp_covert_policy(rs, npc_ok.state, "gm_approved", actor_seat_id="host_1")
    with pytest.raises(PermissionError, match="gm_approved"):
        transfer_scene_item(rs, pol_gm.state, "pc_2", "pc_1", "ruby_seal", gm_approved=False)
    approved_steal = transfer_scene_item(
        rs, pol_gm.state, "pc_2", "pc_1", "ruby_seal", gm_approved=True
    )
    assert "ruby_seal" in approved_steal.state.entity_inventories["pc_1"].items

    # Switch to unrestricted: PC->PC allowed without explicit approval
    pol_unr = set_pvp_covert_policy(
        rs, approved_steal.state, "unrestricted", actor_seat_id="host_1"
    )
    scrut_ok = mark_disguise_seen_through(rs, pol_unr.state, "pc_1", "pc_2")
    assert scrut_ok.active_disguise is not None
    assert "pc_1" in scrut_ok.active_disguise.seen_through_by

    all_events = [
        *d_res.events,
        *dec_pick.events,
        *dec_scrut.events,
        *npc_ok.events,
        *pol_gm.events,
        *approved_steal.events,
        *pol_unr.events,
        *scrut_ok.events,
    ]
    assert state_hash(replay_events(rs, scene, all_events)) == state_hash(scrut_ok.state)


@pytest.mark.zero_ai
def test_covert_ops_validate_graph_catches_bad_references() -> None:
    """RulesetSchema.validate_graph rejects unknown actions, conditions, and awareness levels."""
    rs_bad_stealth = _covert_ruleset(
        stealth=StealthPillarConfig(
            hide_action_ids=("missing_hide",),
            hidden_condition_ids=("missing_cond",),
            detected_level="alert_red",
            unaware_level="asleep",
        ),
        theft=TheftPillarConfig(
            steal_action_ids=("missing_steal",),
        ),
        disguise=DisguisePillarConfig(
            disguise_action_ids=("missing_disguise",),
            disguised_condition_ids=("missing_mask_cond",),
        ),
    )
    errs = rs_bad_stealth.validate_graph()
    joined = "\n".join(errs)
    assert "missing_hide" in joined
    assert "missing_cond" in joined
    assert "alert_red" in joined
    assert "asleep" in joined
    assert "missing_steal" in joined
    assert "missing_disguise" in joined
    assert "missing_mask_cond" in joined

    rs_bad_new = _covert_ruleset(
        stealth=StealthPillarConfig(
            visible_levels=("detected", "nonexistent_vis"),
            sensory_bypass_tags={"unknown_hidden_cond": ("truesight",)},
        ),
        disguise=DisguisePillarConfig(
            source_don_durations_seconds={"invalid_src": 30},
        ),
    )
    errs_new = "\n".join(rs_bad_new.validate_graph())
    assert "nonexistent_vis" in errs_new
    assert "unknown_hidden_cond" in errs_new
    assert "invalid_src" in errs_new


@pytest.mark.zero_ai
def test_stealth_alignment_defaults_awareness_ctx_cached_score_visible_levels_and_bypass() -> None:
    """Validate detected default, visible_levels, bypass tags, stealth_score & @awareness."""
    rs = RulesetSchema(
        manifest=PackageManifest(
            package_type="ruleset",
            package_id="stealth_aligned_ruleset",
            name="Stealth Aligned",
            version="0.1.0",
        ),
        properties={"guile": PropertyBlock(prop_id="guile", label="Guile", default_value=14)},
        conditions={
            "concealed_in_shadow": ConditionBlock(
                condition_id="concealed_in_shadow",
                label="Concealed in Shadow",
            ),
        },
        resolutions={
            "hide_roll": ResolutionMechanicBlock(
                mech_id="hide_roll",
                label="Hide Roll",
                randomizer=RandomizerSpec(kind="none", base_value=16),
                tiers=(
                    OutcomeTier(
                        tier_id="hidden",
                        label="Hidden",
                        condition="true",
                        effects=(
                            EffectSpec(
                                kind="add_condition",
                                target_scope="self",
                                target_key="concealed_in_shadow",
                            ),
                        ),
                    ),
                ),
            ),
            "search_vs_dc": ResolutionMechanicBlock(
                mech_id="search_vs_dc",
                label="Search vs Cached Stealth Score",
                randomizer=RandomizerSpec(kind="none", base_value=18),
                target_formula="@target.stealth_score",
                tiers=(
                    OutcomeTier(
                        tier_id="spotted",
                        label="Spotted",
                        condition="@roll.total >= @target.stealth_score",
                        effects=(
                            EffectSpec(
                                kind="set_awareness",
                                target_scope="target",
                                target_key="exposed",
                            ),
                        ),
                    ),
                ),
            ),
        },
        actions={
            "stealth_roll_hide": ActionBlock(
                action_id="stealth_roll_hide",
                label="Roll Stealth Hide",
                category="action",
                resolution_id="hide_roll",
            ),
            "spot_check": ActionBlock(
                action_id="spot_check",
                label="Spot Check",
                category="action",
                requires_target=True,
                resolution_id="search_vs_dc",
            ),
            "ambush_strike": ActionBlock(
                action_id="ambush_strike",
                label="Ambush Strike",
                category="action",
                requires_target=True,
                requires="@awareness.target_sees_self != 'detected'",
                default_effects=(
                    EffectSpec(
                        kind="advance_clock",
                        target_scope="scene",
                        target_key="ambushes",
                        formula="1",
                    ),
                ),
            ),
        },
        covert_ops=CovertOpsConfigBlock(
            stealth=StealthPillarConfig(
                hide_action_ids=("stealth_roll_hide",),
                hidden_condition_ids=("concealed_in_shadow",),
                awareness_levels=("unaware", "suspected", "exposed", "detected"),
                detected_level="detected",
                unaware_level="unaware",
                visible_levels=("exposed", "detected"),
                sensory_bypass_tags={"concealed_in_shadow": ("truesight",)},
            ),
        ),
    )

    rogue = EntityState(entity_id="pc_1", name="Rogue", is_player_controlled=True)
    guard = EntityState(entity_id="npc_1", name="Normal Guard")
    seer = EntityState(entity_id="npc_2", name="Arcane Seer", tags=("truesight",))
    scene = initialize_scene_state(rs, "aligned_stealth", [rogue, guard, seer])

    # Unhidden target defaults to detected_level (not unaware!)
    assert get_awareness_level(rs, scene, "npc_1", "pc_1") == "detected"
    assert resolve_awareness_level(rs, scene, "npc_1", "pc_1") == "detected"
    assert resolve_target_visibility(rs, scene, "npc_1", "pc_1") is True

    # Dormant stealth pillar never exposes stealth_score in ComputedEntityView
    dormant_rs = _covert_ruleset(include_covert_block=False)
    assert (
        compute_entity_view(
            dormant_rs, rogue.model_copy(update={"stealth_score": 21})
        ).stealth_score
        is None
    )

    # Ambush fails while target detects self
    with pytest.raises(ValueError, match="Precondition failed"):
        execute_action(rs, scene, "pc_1", "ambush_strike", target_id="npc_1")

    # Hide roll automatically caches stealth_score=16 and attaches concealed_in_shadow
    hide_res = execute_action(rs, scene, "pc_1", "stealth_roll_hide")
    s1 = hide_res.state
    assert s1.entities["pc_1"].stealth_score == 16
    assert compute_entity_view(rs, s1.entities["pc_1"]).stealth_score == 16
    assert get_awareness_level(rs, s1, "npc_1", "pc_1") == "unaware"
    assert resolve_target_visibility(rs, s1, "npc_1", "pc_1") is False

    # Observer with sensory bypass tag ('truesight') sees through concealed_in_shadow!
    assert get_awareness_level(rs, s1, "npc_2", "pc_1") == "detected"
    assert resolve_target_visibility(rs, s1, "npc_2", "pc_1") is True

    # @awareness.target_sees_self != 'detected' now allows ambush vs normal guard, fails vs seer
    ambush_res = execute_action(rs, s1, "pc_1", "ambush_strike", target_id="npc_1")
    assert ambush_res.state.clocks["ambushes"] == 1
    with pytest.raises(ValueError, match="Precondition failed"):
        execute_action(rs, ambush_res.state, "pc_1", "ambush_strike", target_id="npc_2")

    # Guard rolls spot_check against @target.stealth_score (18 >= 16) -> sets 'exposed' (visible!)
    spot_res = execute_action(rs, ambush_res.state, "npc_1", "spot_check", target_id="pc_1")
    s2 = spot_res.state
    assert get_awareness_level(rs, s2, "npc_1", "pc_1") == "exposed"
    assert resolve_target_visibility(rs, s2, "npc_1", "pc_1") is True

    manual_score = set_stealth_score(rs, s2, "pc_1", 22)
    assert manual_score.state.entities["pc_1"].stealth_score == 22


@pytest.mark.zero_ai
def test_disguise_preset_crud_linked_outfit_required_items_and_timed_don() -> None:
    """Registered DisguisePreset slots swap linked outfits & support ruleset don durations."""
    rs_timed = _covert_ruleset(
        disguise=DisguisePillarConfig(
            default_don_duration_seconds=300,
            source_don_durations_seconds={"kit": 600, "magical": 6},
        ),
    )
    spy = EntityState(entity_id="pc_1", name="Spy", is_player_controlled=True)
    guard = EntityState(entity_id="npc_1", name="Guard")

    inv = InventoryGraphState()
    tunic = ItemNode(
        item_id="silk_tunic",
        template_id="tunic",
        name="Silk Tunic",
        wearable=WearableLayerSpec(
            layer_id="inner_clothing",
            covered_locations=("torso",),
            appearance_tags=("fine_silk",),
        ),
    )
    kit = ItemNode(item_id="disguise_kit", template_id="kit", name="Master Disguise Kit")
    inv = add_item(inv, tunic)
    inv = wear_item(inv, "silk_tunic")
    inv = save_outfit_preset(inv, "courier_garb", "Courier Attire")
    inv = InventoryGraphState(items=inv.items, outfit_presets=inv.outfit_presets)
    inv = add_item(inv, kit)

    scene = initialize_scene_state(
        rs_timed,
        "wardrobe_scene",
        [spy, guard],
        entity_inventories={"pc_1": inv},
    )

    envoy_slot = DisguisePreset(
        preset_id="envoy_slot",
        label="Envoy Kestrel",
        alias_id="envoy_kestrel",
        presented_name="Envoy Kestrel",
        presented_tags=("diplomat",),
        disguise_source="kit",
        outfit_preset_id="courier_garb",
        required_item_ids=("disguise_kit",),
        voice_disguised=True,
        portrait_override_ref="envoy.png",
    )
    bad_slot = DisguisePreset(
        preset_id="missing_req_slot",
        label="Forger",
        alias_id="forger",
        presented_name="Forger",
        required_item_ids=("missing_wax_seal",),
    )

    s1_res = save_disguise_preset(rs_timed, scene, "pc_1", envoy_slot)
    s2_res = save_disguise_preset(rs_timed, s1_res.state, "pc_1", bad_slot)
    listed = list_disguise_presets(s2_res.state, "pc_1")
    assert [p.preset_id for p in listed] == ["envoy_slot", "missing_req_slot"]

    with pytest.raises(ValueError, match="missing_wax_seal"):
        don_disguise_preset(rs_timed, s2_res.state, "pc_1", "missing_req_slot")

    # Timed kit source duration (600s) stages activity + proposal cleanly
    timed_don = don_disguise_preset(rs_timed, s2_res.state, "pc_1", "envoy_slot", quality_score=19)
    assert timed_don.started_activity is not None
    assert timed_don.started_activity.total_seconds == 600
    assert timed_don.proposed_time_skip is not None
    assert timed_don.state.entities["pc_1"].active_disguise is None

    done = advance_world_time(rs_timed, timed_don.state, 600)
    assert done.state.entities["pc_1"].active_disguise is not None
    assert done.state.entities["pc_1"].active_disguise.alias_id == "envoy_kestrel"
    assert done.state.entities["pc_1"].active_disguise.voice_disguised is True
    assert done.state.entities["pc_1"].active_disguise.quality_score == 19
    assert "silk_tunic" in done.state.entity_inventories["pc_1"].worn_items
    assert "pc_1" not in done.state.active_timed_activities

    # Immediate swap works directly without time skip
    imm_res = don_disguise_preset(
        rs_timed,
        s2_res.state,
        "pc_1",
        "envoy_slot",
        immediate=True,
    )
    assert imm_res.state.entities["pc_1"].active_disguise is not None
    assert "silk_tunic" in imm_res.state.entity_inventories["pc_1"].worn_items

    del_res = delete_disguise_preset(rs_timed, imm_res.state, "pc_1", "missing_req_slot")
    assert [p.preset_id for p in list_disguise_presets(del_res.state, "pc_1")] == ["envoy_slot"]

    all_events = [
        *s1_res.events,
        *s2_res.events,
        *timed_don.events,
        *done.events,
    ]
    assert state_hash(replay_events(rs_timed, scene, all_events)) == state_hash(done.state)
