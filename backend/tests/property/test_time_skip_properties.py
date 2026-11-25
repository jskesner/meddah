"""Hypothesis property tests for Hybrid Synchronized Time Skips (ADR-0135)."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.ruleset_vm import (
    CovertOpsConfigBlock,
    DisguisePillarConfig,
    DisguisePreset,
    EntityState,
    InventoryGraphState,
    ItemNode,
    PackageManifest,
    PropertyBlock,
    RulesetSchema,
    VmEvent,
    WearableLayerSpec,
    add_item,
    advance_world_time,
    cancel_timed_activity,
    commit_time_skip,
    don_disguise_preset,
    gm_trigger_time_skip,
    initialize_scene_state,
    interrupt_time_skip,
    propose_time_skip,
    replay_events,
    save_disguise_preset,
    save_outfit_preset,
    schedule_concurrent_activity,
    start_timed_activity,
    state_hash,
    vote_on_time_skip,
    wear_item,
)


def _prop_time_ruleset() -> RulesetSchema:
    return RulesetSchema(
        manifest=PackageManifest(
            package_type="ruleset",
            package_id="prop_time_skip",
            name="Property Time Skip Ruleset",
            version="0.1.0",
        ),
        properties={"guile": PropertyBlock(prop_id="guile", label="Guile", default_value=10)},
        covert_ops=CovertOpsConfigBlock(
            disguise=DisguisePillarConfig(default_don_duration_seconds=300),
        ),
    )


@pytest.mark.zero_ai
@settings(max_examples=40)
@given(
    ops=st.lists(
        st.tuples(
            st.sampled_from(
                [
                    "start_a",
                    "start_b",
                    "advance",
                    "propose",
                    "schedule_b",
                    "vote_approve",
                    "vote_explore",
                    "interrupt",
                    "cancel_a",
                    "gm_skip",
                ]
            ),
            st.integers(min_value=1, max_value=400),
        ),
        min_size=1,
        max_size=18,
    )
)
def test_time_skip_monotonic_clock_conservation_and_replay_hash(
    ops: list[tuple[str, int]],
) -> None:
    """World time stays monotonic, activity progress sums to total, & replay hash matches."""
    rs = _prop_time_ruleset()
    pc_a = EntityState(entity_id="pc_a", name="Actor A", is_player_controlled=True)
    pc_b = EntityState(entity_id="pc_b", name="Actor B", is_player_controlled=True)
    initial = initialize_scene_state(rs, "prop_time_scene", [pc_a, pc_b])

    cur = initial
    events: list[VmEvent] = []

    for idx, (op, sec) in enumerate(ops):
        prev_elapsed = cur.elapsed_world_seconds
        if op == "start_a":
            res = start_timed_activity(rs, cur, "pc_a", f"Task A {idx}", sec + 60)
        elif op == "start_b":
            res = start_timed_activity(rs, cur, "pc_b", f"Task B {idx}", sec + 60)
        elif op == "advance":
            res = advance_world_time(rs, cur, sec)
        elif op == "propose":
            if cur.pending_time_skip is None or cur.pending_time_skip.status not in {
                "open",
                "held",
            }:
                res = propose_time_skip(
                    rs,
                    cur,
                    "pc_a",
                    f"Skip {idx}",
                    sec + 30,
                    proposer_seat_id="seat_a",
                    required_voter_seat_ids=("seat_a", "seat_b"),
                )
            else:
                res = advance_world_time(rs, cur, 10)
        elif op == "schedule_b":
            if cur.pending_time_skip is not None and cur.pending_time_skip.status in {
                "open",
                "held",
            }:
                res = schedule_concurrent_activity(rs, cur, "pc_b", "Keep Watch")
            else:
                continue
        elif op == "vote_approve":
            if cur.pending_time_skip is not None and cur.pending_time_skip.status in {
                "open",
                "held",
            }:
                res = vote_on_time_skip(rs, cur, "seat_b", "approve")
            else:
                continue
        elif op == "vote_explore":
            if cur.pending_time_skip is not None and cur.pending_time_skip.status in {
                "open",
                "held",
            }:
                res = vote_on_time_skip(rs, cur, "seat_b", "keep_exploring")
            else:
                continue
        elif op == "interrupt":
            res = interrupt_time_skip(rs, cur, sec % 50, reason="noise")
        elif op == "cancel_a":
            res = cancel_timed_activity(rs, cur, "pc_a")
        else:
            res = gm_trigger_time_skip(rs, cur, sec, gm_seat_id="gm_1", seat_role="gm")

        cur = res.state
        events.extend(res.events)
        assert cur.elapsed_world_seconds >= prev_elapsed
        for act in cur.active_timed_activities.values():
            assert act.elapsed_seconds + act.remaining_seconds == act.total_seconds

    if cur.pending_time_skip is not None and cur.pending_time_skip.status == "open":
        fin = commit_time_skip(rs, cur, force=True)
        cur = fin.state
        events.extend(fin.events)

    assert state_hash(replay_events(rs, initial, events)) == state_hash(cur)


@pytest.mark.zero_ai
@settings(max_examples=30)
@given(
    don_seconds=st.integers(min_value=1, max_value=1800),
    ticks=st.lists(st.integers(min_value=1, max_value=600), min_size=1, max_size=8),
)
def test_timed_disguise_preset_completes_exactly_once_and_replays(
    don_seconds: int,
    ticks: list[int],
) -> None:
    """Timed disguise completes cleanly with linked outfit at cumulative >= don_seconds."""
    rs = _prop_time_ruleset()
    pc = EntityState(entity_id="pc_1", name="Chameleon", is_player_controlled=True)
    inv = InventoryGraphState()
    cloak = ItemNode(
        item_id="cape_1",
        template_id="cape",
        name="Silk Cape",
        wearable=WearableLayerSpec(
            layer_id="outer_garment",
            covered_locations=("torso",),
            appearance_tags=("noble_cape",),
        ),
    )
    inv = add_item(inv, cloak)
    inv = wear_item(inv, "cape_1")
    inv = save_outfit_preset(inv, "noble_garb", "Noble Garb")
    inv = InventoryGraphState(items=inv.items, outfit_presets=inv.outfit_presets)

    initial = initialize_scene_state(
        rs,
        "prop_disguise_time",
        [pc],
        entity_inventories={"pc_1": inv},
    )
    saved = save_disguise_preset(
        rs,
        initial,
        "pc_1",
        DisguisePreset(
            preset_id="noble_mask",
            label="Noble Mask",
            alias_id="lord_ash",
            presented_name="Lord Ash",
            outfit_preset_id="noble_garb",
            don_duration_seconds=don_seconds,
        ),
    )
    don_res = don_disguise_preset(
        rs,
        saved.state,
        "pc_1",
        "noble_mask",
        propose_time_skip=False,
    )
    cur = don_res.state
    events: list[VmEvent] = [*saved.events, *don_res.events]
    elapsed = 0

    for dt in ticks:
        adv = advance_world_time(rs, cur, dt)
        cur = adv.state
        events.extend(adv.events)
        elapsed += dt
        if elapsed < don_seconds:
            assert cur.entities["pc_1"].active_disguise is None
        else:
            assert cur.entities["pc_1"].active_disguise is not None
            assert cur.entities["pc_1"].active_disguise.alias_id == "lord_ash"
            assert "cape_1" in cur.entity_inventories["pc_1"].worn_items

    assert state_hash(replay_events(rs, initial, events)) == state_hash(cur)
