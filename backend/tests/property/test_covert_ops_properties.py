"""Hypothesis property tests for Ruleset-Interpreting Covert Operations (ADR-0134)."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.ruleset_vm import (
    CovertOpsConfigBlock,
    DisguisePillarConfig,
    EffectSpec,
    EntityState,
    EventHookBlock,
    InventoryGraphState,
    ItemNode,
    PackageManifest,
    PropertyBlock,
    RulesetSchema,
    StealthPillarConfig,
    TheftPillarConfig,
    VmEvent,
    add_item,
    apply_disguise,
    blow_disguise,
    initialize_scene_state,
    mark_disguise_seen_through,
    mark_scene_item_provenance,
    replay_events,
    set_awareness_level,
    set_pvp_covert_policy,
    state_hash,
    tick_missing_item_notices,
    transfer_scene_item,
)
from app.ruleset_vm.inventory_graph import ProvenanceState


def _prop_covert_ruleset() -> RulesetSchema:
    return RulesetSchema(
        manifest=PackageManifest(
            package_type="ruleset",
            package_id="prop_covert",
            name="Property Covert Ruleset",
            version="0.1.0",
        ),
        properties={"guile": PropertyBlock(prop_id="guile", label="Guile", default_value=12)},
        event_hooks={
            "notice_hook": EventHookBlock(
                hook_id="notice_hook",
                event_name="on_missing_item_noticed",
                effects=(
                    EffectSpec(
                        kind="advance_clock",
                        target_scope="scene",
                        target_key="alerts",
                        formula="1",
                    ),
                ),
            ),
        },
        covert_ops=CovertOpsConfigBlock(
            stealth=StealthPillarConfig(),
            theft=TheftPillarConfig(default_notice_delay_turns=2),
            disguise=DisguisePillarConfig(),
        ),
    )


@pytest.mark.zero_ai
@settings(max_examples=40)
@given(
    ops=st.lists(
        st.tuples(
            st.integers(min_value=0, max_value=2),
            st.integers(min_value=0, max_value=2),
            st.integers(min_value=0, max_value=2),
            st.sampled_from(["stolen", "planted", "contraband", "legitimate"]),
        ),
        min_size=1,
        max_size=14,
    ),
)
def test_item_transfer_and_provenance_conserve_items_and_replay_hash(
    ops: list[tuple[int, int, int, ProvenanceState]],
) -> None:
    """Arbitrary item transfers and provenance changes strictly conserve item IDs & replay hash."""
    rs = _prop_covert_ruleset()
    entity_ids = ("pc_1", "npc_1", "npc_2")
    entities = [
        EntityState(entity_id="pc_1", name="PC", is_player_controlled=True),
        EntityState(entity_id="npc_1", name="NPC One"),
        EntityState(entity_id="npc_2", name="NPC Two"),
    ]
    inventories: dict[str, InventoryGraphState] = {eid: InventoryGraphState() for eid in entity_ids}
    expected_ids: set[str] = set()
    for idx, owner_id in enumerate(entity_ids):
        item_id = f"relic_{idx}"
        expected_ids.add(item_id)
        inventories[owner_id] = add_item(
            inventories[owner_id],
            ItemNode(
                item_id=item_id,
                template_id="relic",
                name=f"Relic {idx}",
                owner_entity_id=owner_id,
            ),
        )

    initial = initialize_scene_state(
        rs,
        "prop_transfer_scene",
        entities,
        entity_inventories=inventories,
        pvp_covert_policy="unrestricted",
    )
    cur = initial
    events: list[VmEvent] = []

    for item_idx, dst_idx, _, prov in ops:
        item_id = f"relic_{item_idx}"
        src_id = next(eid for eid in entity_ids if item_id in cur.entity_inventories[eid].items)
        dst_id = entity_ids[dst_idx]
        if src_id == dst_id:
            res = mark_scene_item_provenance(rs, cur, src_id, item_id, prov)
        else:
            res = transfer_scene_item(rs, cur, src_id, dst_id, item_id, provenance_state=prov)
        cur = res.state
        events.extend(res.events)

        present_ids: list[str] = []
        for eid in entity_ids:
            present_ids.extend(cur.entity_inventories[eid].items.keys())
        assert len(present_ids) == len(expected_ids)
        assert set(present_ids) == expected_ids

    replayed = replay_events(rs, initial, events)
    assert state_hash(replayed) == state_hash(cur)


@pytest.mark.zero_ai
@settings(max_examples=40)
@given(
    steps=st.lists(
        st.sampled_from(
            [
                "aware_suspected",
                "aware_detected",
                "aware_unaware",
                "disguise_apply",
                "disguise_scrutinize",
                "disguise_blow",
                "policy_gm",
                "policy_unrestricted",
                "tick_notice",
                "steal_or_return",
            ]
        ),
        min_size=1,
        max_size=20,
    ),
)
def test_covert_state_machine_replay_determinism(steps: list[str]) -> None:
    """Arbitrary sequences across all 3 covert pillars replay to an identical state hash."""
    rs = _prop_covert_ruleset()
    rogue = EntityState(entity_id="pc_1", name="Rogue", is_player_controlled=True)
    guard = EntityState(entity_id="npc_1", name="Guard")
    guard_inv = add_item(
        InventoryGraphState(),
        ItemNode(item_id="cipher_key", template_id="key", name="Cipher Key"),
    )
    initial = initialize_scene_state(
        rs,
        "prop_fsm",
        [rogue, guard],
        entity_inventories={"pc_1": InventoryGraphState(), "npc_1": guard_inv},
    )
    cur = initial
    events: list[VmEvent] = []

    for idx, step in enumerate(steps):
        if step == "aware_suspected":
            res = set_awareness_level(rs, cur, "npc_1", "pc_1", "suspected")
        elif step == "aware_detected":
            res = set_awareness_level(rs, cur, "npc_1", "pc_1", "detected")
        elif step == "aware_unaware":
            res = set_awareness_level(rs, cur, "npc_1", "pc_1", "unaware")
        elif step == "disguise_apply":
            res = apply_disguise(rs, cur, "pc_1", f"alias_{idx}", f"Persona {idx}")
        elif step == "disguise_scrutinize":
            res = mark_disguise_seen_through(rs, cur, "npc_1", "pc_1")
        elif step == "disguise_blow":
            res = blow_disguise(rs, cur, "pc_1")
        elif step == "policy_gm":
            res = set_pvp_covert_policy(rs, cur, "gm_approved", actor_seat_id="host_1")
        elif step == "policy_unrestricted":
            res = set_pvp_covert_policy(rs, cur, "unrestricted", actor_seat_id="host_1")
        elif step == "tick_notice":
            res = tick_missing_item_notices(rs, cur, turns=1)
        else:
            if "cipher_key" in cur.entity_inventories["npc_1"].items:
                res = transfer_scene_item(rs, cur, "npc_1", "pc_1", "cipher_key")
            else:
                res = transfer_scene_item(
                    rs, cur, "pc_1", "npc_1", "cipher_key", provenance_state="legitimate"
                )
        cur = res.state
        events.extend(res.events)

    replayed = replay_events(rs, initial, events)
    assert state_hash(replayed) == state_hash(cur)
