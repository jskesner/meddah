"""Hypothesis property tests for InventoryGraph and Character Creation invariants."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.ruleset_vm import (
    CapacityRule,
    EntityState,
    GridPlacement,
    InventoryGraphState,
    ItemNode,
    PackageManifest,
    PointBuyStepSpec,
    RulesetSchema,
    add_item,
    apply_point_buy,
    equip_to_node,
    start_creation_session,
    sync_inventory_auras_to_entity,
    total_carried_weight,
    unequip_node,
)
from app.ruleset_vm.advancement import CreationGraphSpec


@pytest.mark.zero_ai
@given(
    weights=st.lists(
        st.floats(min_value=0.0, max_value=25.0, allow_nan=False, allow_infinity=False), max_size=10
    ),
    quantities=st.lists(st.integers(min_value=1, max_value=5), max_size=10),
)
def test_inventory_weight_is_strictly_additive(
    weights: list[float],
    quantities: list[int],
) -> None:
    """Adding items into unlimited root sums exactly to sum(unit_weight * quantity)."""
    pairs = list(zip(weights, quantities, strict=False))
    graph = InventoryGraphState(root_capacity=CapacityRule(mode="unlimited"))
    expected = 0.0
    for idx, (u_w, qty) in enumerate(pairs):
        item = ItemNode(
            item_id=f"item_{idx}",
            template_id="tpl",
            name=f"Item {idx}",
            quantity=qty,
            unit_weight=u_w,
        )
        graph = add_item(graph, item)
        expected += u_w * qty
    assert total_carried_weight(graph) == pytest.approx(expected)


@pytest.mark.zero_ai
@given(
    items_dims=st.lists(
        st.tuples(st.integers(min_value=1, max_value=2), st.integers(min_value=1, max_value=2)),
        min_size=1,
        max_size=6,
    )
)
def test_grid_2d_auto_placement_never_overlaps(items_dims: list[tuple[int, int]]) -> None:
    """Auto-placed grid items remain strictly within grid bounds and never overlap."""
    grid_w, grid_h = 8, 8
    graph = InventoryGraphState(
        root_capacity=CapacityRule(mode="grid_2d", grid_width=grid_w, grid_height=grid_h)
    )
    for idx, (iw, ih) in enumerate(items_dims):
        graph = add_item(
            graph,
            ItemNode(
                item_id=f"g_{idx}",
                template_id="g",
                name=f"G {idx}",
                grid_width=iw,
                grid_height=ih,
            ),
        )

    occupied_cells: set[tuple[int, int]] = set()
    for item_id, pos in graph.grid_placements.items():
        assert isinstance(pos, GridPlacement)
        node = graph.items[item_id]
        eff_w = node.grid_height if pos.rotated else node.grid_width
        eff_h = node.grid_width if pos.rotated else node.grid_height
        assert pos.x + eff_w <= grid_w
        assert pos.y + eff_h <= grid_h
        for dx in range(eff_w):
            for dy in range(eff_h):
                cell = (pos.x + dx, pos.y + dy)
                assert cell not in occupied_cells
                occupied_cells.add(cell)


@pytest.mark.zero_ai
@given(bonus=st.integers(min_value=-10, max_value=10))
def test_equip_unequip_aura_round_trip_identity(bonus: int) -> None:
    """Equipping then unequipping an item leaves zero leftover auras or granted actions."""
    graph = InventoryGraphState(attachment_nodes=("main_hand",))
    relic = ItemNode(
        item_id="relic_1",
        template_id="relic",
        name="Focus",
        attachable_nodes=("main_hand",),
        passive_aura_modifiers={"defense": bonus},
        granted_actions=("focus_strike",),
    )
    graph = add_item(graph, relic)
    ent = EntityState(entity_id="pc", name="Hero")

    equipped = equip_to_node(graph, "relic_1", "main_hand")
    ent_eq = sync_inventory_auras_to_entity(ent, equipped)
    assert ent_eq.aura_modifiers["defense"] == bonus
    assert ent_eq.granted_actions == ("focus_strike",)

    unequipped = unequip_node(equipped, "main_hand")
    ent_clean = sync_inventory_auras_to_entity(ent_eq, unequipped)
    assert ent_clean.aura_modifiers == {}
    assert ent_clean.granted_actions == ()


@pytest.mark.zero_ai
@given(
    a=st.integers(min_value=8, max_value=15),
    b=st.integers(min_value=8, max_value=15),
)
def test_point_buy_budget_invariant(a: int, b: int) -> None:
    """Point buy accepts iff sum(scores - 8) <= budget."""
    rs = RulesetSchema(
        manifest=PackageManifest(
            package_type="ruleset",
            package_id="pb_prop",
            name="Point Buy Prop",
            version="0.1.0",
        )
    )
    step = PointBuyStepSpec(
        step_id="pb",
        label="Point Buy",
        target_properties=("brawn", "agility"),
        budget_points=8,
        base_value=8,
        min_score=8,
        max_score=15,
    )
    session = start_creation_session(CreationGraphSpec(steps=(step,)), rs, entity_id="pc", name="N")
    cost = (a - 8) + (b - 8)
    if cost <= 8:
        updated = apply_point_buy(session, step, {"brawn": a, "agility": b})
        assert updated.base_properties["brawn"] == a
        assert updated.base_properties["agility"] == b
    else:
        with pytest.raises(ValueError, match="exceeds budget"):
            apply_point_buy(session, step, {"brawn": a, "agility": b})
