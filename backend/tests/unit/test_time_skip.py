"""Unit tests for Hybrid Synchronized Time Skips & Non-Blocking Timed Activities (ADR-0135)."""

from __future__ import annotations

import pytest

from app.ruleset_vm import (
    TIME_SKIP_MODULE_MANIFEST,
    ActionBlock,
    CovertOpsConfigBlock,
    DisguisePillarConfig,
    DisguisePreset,
    EffectSpec,
    EntityState,
    EventHookBlock,
    InventoryGraphState,
    ItemNode,
    ModuleRegistry,
    PackageManifest,
    PropertyBlock,
    RulesetSchema,
    VmEvent,
    WearableLayerSpec,
    add_item,
    advance_world_time,
    apply_event,
    cancel_timed_activity,
    commit_time_skip,
    don_disguise_preset,
    gm_trigger_time_skip,
    initialize_scene_state,
    interrupt_time_skip,
    propose_time_skip,
    replay_events,
    resolve_cross_branch_comm_delivery_mode,
    save_disguise_preset,
    save_outfit_preset,
    schedule_concurrent_activity,
    start_timed_activity,
    state_hash,
    vote_on_time_skip,
    wear_item,
)


def _time_skip_ruleset() -> RulesetSchema:
    return RulesetSchema(
        manifest=PackageManifest(
            package_type="ruleset",
            package_id="time_skip_test",
            name="Time Skip Test",
            version="0.1.0",
        ),
        properties={"guile": PropertyBlock(prop_id="guile", label="Guile", default_value=12)},
        actions={
            "flip_switch": ActionBlock(
                action_id="flip_switch",
                label="Flip Switch",
                category="action",
                default_effects=(
                    EffectSpec(
                        kind="advance_clock",
                        target_scope="scene",
                        target_key="vault_door_open",
                        formula="1",
                    ),
                ),
            ),
            "keep_watch": ActionBlock(
                action_id="keep_watch",
                label="Keep Watch",
                category="action",
            ),
        },
        event_hooks={
            "hook_world": EventHookBlock(
                hook_id="hook_world",
                event_name="on_world_time_advanced",
                effects=(
                    EffectSpec(
                        kind="advance_clock",
                        target_scope="scene",
                        target_key="world_adv_hooks",
                        formula="1",
                    ),
                ),
            ),
            "hook_act_start": EventHookBlock(
                hook_id="hook_act_start",
                event_name="on_timed_activity_started",
                effects=(
                    EffectSpec(
                        kind="advance_clock",
                        target_scope="scene",
                        target_key="act_start_hooks",
                        formula="1",
                    ),
                ),
            ),
            "hook_act_done": EventHookBlock(
                hook_id="hook_act_done",
                event_name="on_timed_activity_completed",
                effects=(
                    EffectSpec(
                        kind="advance_clock",
                        target_scope="scene",
                        target_key="act_done_hooks",
                        formula="1",
                    ),
                ),
            ),
            "hook_act_int": EventHookBlock(
                hook_id="hook_act_int",
                event_name="on_timed_activity_interrupted",
                effects=(
                    EffectSpec(
                        kind="advance_clock",
                        target_scope="scene",
                        target_key="act_int_hooks",
                        formula="1",
                    ),
                ),
            ),
            "hook_skip_int": EventHookBlock(
                hook_id="hook_skip_int",
                event_name="on_time_skip_interrupted",
                effects=(
                    EffectSpec(
                        kind="advance_clock",
                        target_scope="scene",
                        target_key="skip_int_hooks",
                        formula="1",
                    ),
                ),
            ),
            "hook_skip_commit": EventHookBlock(
                hook_id="hook_skip_commit",
                event_name="on_time_skip_committed",
                effects=(
                    EffectSpec(
                        kind="advance_clock",
                        target_scope="scene",
                        target_key="skip_commit_hooks",
                        formula="1",
                    ),
                ),
            ),
            "hook_disguise": EventHookBlock(
                hook_id="hook_disguise",
                event_name="on_disguise_applied",
                effects=(
                    EffectSpec(
                        kind="advance_clock",
                        target_scope="scene",
                        target_key="disguise_hooks",
                        formula="1",
                    ),
                ),
            ),
        },
        covert_ops=CovertOpsConfigBlock(
            disguise=DisguisePillarConfig(default_don_duration_seconds=600),
        ),
    )


@pytest.mark.zero_ai
def test_time_skip_manifest_and_toggle_round_trip() -> None:
    """TIME_SKIP_MODULE_MANIFEST activates with zero mandatory primitives & replays cleanly."""
    reg = ModuleRegistry()
    reg.register(TIME_SKIP_MODULE_MANIFEST)
    assert reg.resolve_status("synchronized_time_skip", ()).state == "available"
    reg.set_enabled("synchronized_time_skip", True)
    assert reg.resolve_status("synchronized_time_skip", ()).state == "active"

    rs = _time_skip_ruleset()
    pc = EntityState(entity_id="pc_1", name="Scout", is_player_controlled=True)
    initial = initialize_scene_state(
        rs,
        "ts_mod_scene",
        [pc],
        active_modules=("synchronized_time_skip",),
    )
    off_evt = VmEvent(
        event_id="evt_ts_off",
        event_type="MODULE_OVERRIDE",
        actor_id="host",
        payload={"module_id": "synchronized_time_skip", "enabled": False},
    )
    on_evt = VmEvent(
        event_id="evt_ts_on",
        event_type="MODULE_OVERRIDE",
        actor_id="host",
        payload={"module_id": "synchronized_time_skip", "enabled": True},
    )
    s1 = apply_event(rs, initial, off_evt)
    s2 = apply_event(rs, s1, on_evt)
    assert s2.active_modules == ("synchronized_time_skip",)
    assert state_hash(replay_events(rs, initial, [off_evt, on_evt])) == state_hash(s2)


@pytest.mark.zero_ai
def test_hybrid_split_room_non_blocking_exploration_and_concurrent_sync() -> None:
    """Group A dons a 10m disguise while Group B keeps exploring, then catches up remaining 8m."""
    rs = _time_skip_ruleset()
    pc_a = EntityState(entity_id="pc_1", name="Infiltrator", is_player_controlled=True)
    pc_b = EntityState(entity_id="pc_2", name="Scout", is_player_controlled=True)

    inv_a = InventoryGraphState()
    coat = ItemNode(
        item_id="guard_coat",
        template_id="coat",
        name="Watch Coat",
        wearable=WearableLayerSpec(
            layer_id="outer_garment",
            covered_locations=("torso",),
            appearance_tags=("city_watch",),
        ),
    )
    inv_a = add_item(inv_a, coat)
    inv_a = wear_item(inv_a, "guard_coat")
    inv_a = save_outfit_preset(inv_a, "watch_uniform", "City Watch Uniform")
    inv_a = InventoryGraphState(
        items=inv_a.items,
        outfit_presets=inv_a.outfit_presets,
    )

    scene = initialize_scene_state(
        rs,
        "split_facility",
        [pc_a, pc_b],
        entity_inventories={"pc_1": inv_a, "pc_2": InventoryGraphState()},
    )
    saved = save_disguise_preset(
        rs,
        scene,
        "pc_1",
        DisguisePreset(
            preset_id="watch_persona",
            label="City Watch Disguise",
            alias_id="corporal_bren",
            presented_name="Corporal Bren",
            presented_tags=("watch",),
            outfit_preset_id="watch_uniform",
        ),
    )
    assert saved.state.entities["pc_1"].active_disguise is None

    # PC A in boiler_room begins donning 10-minute (600s) disguise + opens skip proposal
    don_res = don_disguise_preset(
        rs,
        saved.state,
        "pc_1",
        "watch_persona",
        actor_seat_id="seat_1",
        required_voter_seat_ids=("seat_1", "seat_2"),
        room_id="boiler_room",
    )
    s1 = don_res.state
    assert s1.entities["pc_1"].active_disguise is None
    assert s1.active_timed_activities["pc_1"].remaining_seconds == 600
    assert s1.pending_time_skip is not None

    # PC B chooses keep_exploring: table proposal dismisses without canceling PC A's activity
    keep_res = vote_on_time_skip(rs, s1, "seat_2", "keep_exploring")
    s2 = keep_res.state
    assert s2.pending_time_skip is None
    assert s2.active_timed_activities["pc_1"].remaining_seconds == 600

    # Group B explores hallway for 120s and unlocks shared switch — single clock stays consistent!
    adv_b = advance_world_time(rs, s2, 120, actor_seat_id="seat_2", reason="hallway_explore")
    s3 = adv_b.state
    assert s3.elapsed_world_seconds == 120
    assert s3.active_timed_activities["pc_1"].elapsed_seconds == 120
    assert s3.active_timed_activities["pc_1"].remaining_seconds == 480
    assert s3.entities["pc_1"].active_disguise is None

    # Now Group B catches up for the remaining 480s while keeping watch concurrently
    prop2 = propose_time_skip(
        rs,
        s3,
        "pc_2",
        "Catch up for PC 1 disguise",
        480,
        proposer_seat_id="seat_2",
        required_voter_seat_ids=("seat_1", "seat_2"),
    )
    sched_b = schedule_concurrent_activity(
        rs,
        prop2.state,
        "pc_2",
        "Keep Watch at Junction",
        category="watch",
        action_id="keep_watch",
        actor_seat_id="seat_2",
    )
    assert sched_b.state.pending_time_skip is not None
    assert "pc_2" in sched_b.state.pending_time_skip.concurrent_activities

    vote_a = vote_on_time_skip(rs, sched_b.state, "seat_1", "approve")
    s4 = vote_a.state
    assert s4.elapsed_world_seconds == 600
    assert s4.pending_time_skip is None
    assert "pc_1" not in s4.active_timed_activities
    assert s4.entities["pc_1"].active_disguise is not None
    assert s4.entities["pc_1"].active_disguise.alias_id == "corporal_bren"
    assert "guard_coat" in s4.entity_inventories["pc_1"].worn_items
    assert s4.clocks["disguise_hooks"] == 1
    assert s4.clocks["act_done_hooks"] == 1
    assert s4.clocks["skip_commit_hooks"] == 1

    all_events = [
        *saved.events,
        *don_res.events,
        *keep_res.events,
        *adv_b.events,
        *prop2.events,
        *sched_b.events,
        *vote_a.events,
    ]
    assert state_hash(replay_events(rs, scene, all_events)) == state_hash(s4)


@pytest.mark.zero_ai
def test_votes_hold_majority_gm_only_and_partial_interruptions() -> None:
    """Verify hold_act_first, consensus modes, cancel, and mid-skip partial progress."""
    rs = _time_skip_ruleset()
    pc_1 = EntityState(entity_id="pc_1", name="PC 1", is_player_controlled=True)
    pc_2 = EntityState(entity_id="pc_2", name="PC 2", is_player_controlled=True)
    pc_3 = EntityState(entity_id="pc_3", name="PC 3", is_player_controlled=True)
    scene = initialize_scene_state(rs, "vote_scene", [pc_1, pc_2, pc_3])

    act_res = start_timed_activity(
        rs,
        scene,
        "pc_1",
        "Bandage Wounds",
        600,
        category="rest",
        actor_seat_id="seat_1",
    )
    prop_res = propose_time_skip(
        rs,
        act_res.state,
        "pc_1",
        "10m Short Breather",
        600,
        proposer_seat_id="seat_1",
        required_voter_seat_ids=("seat_1", "seat_2", "seat_3"),
        consensus_mode="majority",
    )

    # Hold blocks non-forced commit
    hold_res = vote_on_time_skip(rs, prop_res.state, "seat_2", "hold_act_first")
    assert hold_res.state.pending_time_skip is not None
    assert hold_res.state.pending_time_skip.status == "held"
    with pytest.raises(PermissionError, match="held"):
        commit_time_skip(rs, hold_res.state, actor_seat_id="seat_1", force=False)

    # Clear hold & test majority consensus once 2 of 3 approve? Interrupt first to check partial!
    unhold = vote_on_time_skip(
        rs,
        hold_res.state,
        "seat_2",
        "approve",
        auto_commit_on_consensus=False,
    )
    assert unhold.state.pending_time_skip is not None
    assert unhold.state.pending_time_skip.status == "open"

    # Ambush interrupts after 180s -> 420s remains preserved on paused activity
    int_res = interrupt_time_skip(
        rs,
        unhold.state,
        180,
        reason="patrol_ambush",
        actor_seat_id="gm_1",
    )
    s_int = int_res.state
    assert s_int.elapsed_world_seconds == 180
    assert s_int.active_timed_activities["pc_1"].status == "paused"
    assert s_int.active_timed_activities["pc_1"].elapsed_seconds == 180
    assert s_int.active_timed_activities["pc_1"].remaining_seconds == 420
    assert s_int.pending_time_skip is not None
    assert s_int.pending_time_skip.status == "interrupted"
    assert s_int.pending_time_skip.interrupted_reason == "patrol_ambush"
    assert s_int.clocks["skip_int_hooks"] == 1
    assert s_int.clocks["act_int_hooks"] == 1

    # Cancel paused activity fires interruption hook and clears map
    cancel_res = cancel_timed_activity(rs, s_int, "pc_1", reason="aborted", actor_seat_id="seat_1")
    assert "pc_1" not in cancel_res.state.active_timed_activities
    assert cancel_res.state.clocks["act_int_hooks"] == 2

    # Test gm_only consensus mode never auto-commits on player approval
    gm_prop = propose_time_skip(
        rs,
        cancel_res.state,
        "pc_1",
        "Travel Overnight",
        3600,
        proposer_seat_id="seat_1",
        required_voter_seat_ids=("seat_1", "seat_2"),
        consensus_mode="gm_only",
    )
    gm_vote = vote_on_time_skip(rs, gm_prop.state, "seat_2", "approve")
    assert gm_vote.state.elapsed_world_seconds == 180
    assert gm_vote.state.pending_time_skip is not None

    all_events = [
        *act_res.events,
        *prop_res.events,
        *hold_res.events,
        *unhold.events,
        *int_res.events,
        *cancel_res.events,
        *gm_prop.events,
        *gm_vote.events,
    ]
    assert state_hash(replay_events(rs, scene, all_events)) == state_hash(gm_vote.state)


@pytest.mark.zero_ai
def test_gm_trigger_rbac_and_cross_branch_comms_isolation() -> None:
    """GM/Co-GM/Host can manually skip or prompt; players are blocked; CoW branches queue comms."""
    rs = _time_skip_ruleset()
    pc_1 = EntityState(entity_id="pc_1", name="Hero", is_player_controlled=True)
    scene = initialize_scene_state(rs, "gm_scene", [pc_1])

    with pytest.raises(PermissionError, match="not authorized"):
        gm_trigger_time_skip(
            rs,
            scene,
            600,
            gm_seat_id="seat_player",
            seat_role="player",
        )

    prompt_res = gm_trigger_time_skip(
        rs,
        scene,
        1800,
        label="Await Dawn Ferry",
        gm_seat_id="gm_1",
        seat_role="gm",
        prompt_players=True,
        required_voter_seat_ids=("seat_1",),
    )
    assert prompt_res.state.pending_time_skip is not None
    assert prompt_res.state.elapsed_world_seconds == 0

    direct_res = gm_trigger_time_skip(
        rs,
        prompt_res.state,
        1800,
        label="Dawn Arrives",
        gm_seat_id="gm_1",
        seat_role="host",
        prompt_players=False,
    )
    assert direct_res.state.pending_time_skip is None
    assert direct_res.state.elapsed_world_seconds == 1800
    assert state_hash(
        replay_events(rs, scene, [*prompt_res.events, *direct_res.events])
    ) == state_hash(direct_res.state)

    assert resolve_cross_branch_comm_delivery_mode(True, "mental_link") == "live_synchronous"
    assert resolve_cross_branch_comm_delivery_mode(False, "mental_link") == "queue_until_settlement"
    assert (
        resolve_cross_branch_comm_delivery_mode(False, "tuned_frequency")
        == "queue_until_settlement"
    )
