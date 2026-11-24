"""Unit tests for Universal Composable Container Graph & Layered Apparel Stacking."""

from __future__ import annotations

import pytest

from app.ruleset_vm import (
    CapacityRule,
    EntityState,
    GridPlacement,
    InventoryGraphState,
    ItemNode,
    WearableLayerSpec,
    add_item,
    apply_outfit_preset,
    compute_visible_appearance,
    equip_to_node,
    move_item,
    remove_item,
    save_outfit_preset,
    set_transmog_override,
    sync_inventory_auras_to_entity,
    total_abstract_load,
    total_carried_slots,
    total_carried_weight,
    unequip_node,
    wear_item,
)


@pytest.mark.zero_ai
def test_nested_weight_formula_slots_load_and_cycle_prevention() -> None:
    """Container weights aggregate recursively; cycles and overflows are rejected."""
    graph = InventoryGraphState(
        root_capacity=CapacityRule(mode="weight", max_weight_formula="@self.brawn * 15")
    )
    ctx = {"@self": {"brawn": 2}}  # 30.0 max weight

    pack = ItemNode(
        item_id="pack_1",
        template_id="expedition_pack",
        name="Expedition Pack",
        unit_weight=2.0,
        container_capacity=CapacityRule(mode="slots", max_slots=4),
    )
    sub_pouch = ItemNode(
        item_id="pouch_1",
        template_id="coin_pouch",
        name="Belt Pouch",
        unit_weight=0.5,
        slot_size=1,
        container_capacity=CapacityRule(mode="weight", max_weight=10.0),
    )
    ration_bar = ItemNode(
        item_id="ration_1",
        template_id="ration",
        name="Travel Rations",
        quantity=3,
        unit_weight=2.0,
        slot_size=1,
    )

    graph = add_item(graph, pack, owner_ctx=ctx)
    graph = add_item(graph, sub_pouch, container_id="pack_1", owner_ctx=ctx)
    graph = add_item(graph, ration_bar, container_id="pouch_1", owner_ctx=ctx)

    assert total_carried_weight(graph) == pytest.approx(8.5)
    assert total_carried_slots(graph, "pack_1") == 1

    # Ancestor cycle prevention: cannot place pack inside its child pouch
    with pytest.raises(ValueError, match="descendant"):
        move_item(graph, "pack_1", "pouch_1", owner_ctx=ctx)

    # Cannot add 25.0 unit weight into pouch_1 (exceeds pouch cap 10.0 & root cap 30.0)
    heavy_ingot = ItemNode(
        item_id="ingot_1",
        template_id="iron_ingot",
        name="Heavy Ingot",
        unit_weight=12.0,
    )
    with pytest.raises(ValueError, match="Weight capacity exceeded"):
        add_item(graph, heavy_ingot, container_id="pouch_1", owner_ctx=ctx)

    # Non-empty container requires cascade=True to remove
    with pytest.raises(ValueError, match="non-empty"):
        remove_item(graph, "pack_1")
    emptied = remove_item(graph, "pack_1", cascade=True)
    assert emptied.items == {}

    # Abstract load mode
    load_graph = InventoryGraphState(
        root_capacity=CapacityRule(
            mode="abstract_load",
            load_tiers={"light": 3, "normal": 5, "heavy": 6},
            selected_load_tier="light",
        )
    )
    gear = ItemNode(item_id="kit_1", template_id="kit", name="Pry Bar", load_cost=2)
    rope = ItemNode(item_id="rope_1", template_id="rope", name="Climbing Rope", load_cost=2)
    load_graph = add_item(load_graph, gear)
    assert total_abstract_load(load_graph) == 2
    with pytest.raises(ValueError, match="Abstract load"):
        add_item(load_graph, rope)


@pytest.mark.zero_ai
def test_grid_2d_bounds_collision_and_rotation() -> None:
    """2D grid inventory enforces bounds, collision detection, and rotated placement."""
    grid_inv = InventoryGraphState(
        root_capacity=CapacityRule(mode="grid_2d", grid_width=4, grid_height=3)
    )
    long_case = ItemNode(
        item_id="case_1",
        template_id="rifle_case",
        name="Long Case",
        grid_width=3,
        grid_height=1,
    )
    med_kit = ItemNode(
        item_id="med_1",
        template_id="trauma_kit",
        name="Trauma Kit",
        grid_width=2,
        grid_height=2,
    )

    grid_inv = add_item(grid_inv, long_case, grid_pos=GridPlacement(x=0, y=0))
    # Overlapping cell at (2, 0) fails
    with pytest.raises(ValueError, match="does not fit"):
        add_item(grid_inv, med_kit, grid_pos=GridPlacement(x=2, y=0))

    # Placing below at (0, 1) fits
    grid_inv = add_item(grid_inv, med_kit, grid_pos=GridPlacement(x=0, y=1))

    # Rotating a 2x1 flask into a 1x2 column fits at (3, 1)
    tall_flask = ItemNode(
        item_id="flask_1",
        template_id="flask",
        name="Alchemical Flask",
        grid_width=2,
        grid_height=1,
    )
    grid_inv = add_item(grid_inv, tall_flask, grid_pos=GridPlacement(x=3, y=1, rotated=True))
    assert grid_inv.grid_placements["flask_1"].rotated is True


@pytest.mark.zero_ai
def test_universal_anatomical_layering_concealment_transmog_outfits_and_auras() -> None:
    """Anatomical stacking works decoupled from hit locations with RAW transmog & outfits."""
    graph = InventoryGraphState(
        layering_mode="anatomical_layered",
        attachment_nodes=("main_hand", "waist"),
    )

    silk_shirt = ItemNode(
        item_id="shirt_1",
        template_id="silk_shirt",
        name="Fine Silk Shirt",
        wearable=WearableLayerSpec(
            layer_id="inner_clothing",
            covered_locations=("torso", "left_arm", "right_arm"),
            appearance_tags=("fine_attire",),
            climate_tags=("breathable",),
            don_action_cost=1,
            doff_action_cost=1,
        ),
    )
    mail_shirt = ItemNode(
        item_id="mail_1",
        template_id="chain_shirt",
        name="Riveted Mail Shirt",
        wearable=WearableLayerSpec(
            layer_id="protective_armor",
            covered_locations=("torso", "left_arm", "right_arm"),
            appearance_tags=("armored",),
            don_action_cost=3,
            doff_action_cost=3,
            mitigation_value=4,
        ),
        passive_aura_modifiers={"defense": 3},
        granted_actions=("brace_armor",),
    )
    leather_jerkin = ItemNode(
        item_id="jerkin_1",
        template_id="leather_jerkin",
        name="Studded Jerkin",
        wearable=WearableLayerSpec(
            layer_id="protective_armor",
            covered_locations=("torso",),
            mitigation_value=2,
        ),
    )
    greatcoat = ItemNode(
        item_id="coat_1",
        template_id="greatcoat",
        name="Heavy Trenchcoat",
        wearable=WearableLayerSpec(
            layer_id="outer_garment",
            covered_locations=("torso", "left_arm", "right_arm", "legs"),
            conceals_inner_layers=True,
            appearance_tags=("noble_coat",),
            climate_tags=("cold_weather",),
            don_action_cost=1,
            doff_action_cost=1,
            mitigation_value=1,
        ),
    )
    holdout_dagger = ItemNode(
        item_id="dagger_1",
        template_id="stiletto",
        name="Concealed Stiletto",
        attachable_nodes=("waist", "main_hand"),
        concealable=True,
        granted_actions=("quick_slash",),
    )

    for node in (silk_shirt, mail_shirt, leather_jerkin, greatcoat, holdout_dagger):
        graph = add_item(graph, node)

    graph = wear_item(graph, "shirt_1")
    graph = wear_item(graph, "mail_1")
    # Same layer ("protective_armor") + overlapping location ("torso") rejected
    with pytest.raises(ValueError, match="already occupied"):
        wear_item(graph, "jerkin_1")

    graph = wear_item(graph, "coat_1")
    graph = equip_to_node(graph, "dagger_1", "waist")

    snap = compute_visible_appearance(graph)
    assert snap.visible_by_location["torso"] == "coat_1"
    assert snap.concealed_item_ids == ("dagger_1", "mail_1", "shirt_1")
    assert snap.location_mitigation["torso"] == 5
    assert snap.active_climate_tags == ("breathable", "cold_weather")
    assert snap.active_appearance_tags == ("noble_coat",)

    # Sync passive auras & granted actions onto EntityState
    ent = EntityState(entity_id="pc_1", name="Operative")
    synced = sync_inventory_auras_to_entity(ent, graph)
    assert synced.aura_modifiers == {"defense": 3}
    assert synced.granted_actions == ("brace_armor", "quick_slash")

    # RAW cosmetic_transmog_enabled=False blocks transmog overrides by default
    with pytest.raises(PermissionError):
        set_transmog_override(graph, "torso", "shirt_1")

    transmog_enabled = set_transmog_override(
        graph.model_copy(update={"cosmetic_transmog_enabled": True}),
        "torso",
        "shirt_1",
    )
    assert compute_visible_appearance(transmog_enabled).visible_by_location["torso"] == "shirt_1"

    # Outfit presets: instant outside combat, don/doff cost gated inside structured combat
    with_presets = save_outfit_preset(graph, "combat_coat", "Coat & Mail")
    naked_graph = with_presets.model_copy(update={"worn_items": (), "attachments": {}})
    naked_graph = save_outfit_preset(naked_graph, "civilian", "Plain")

    restored, free_cost = apply_outfit_preset(
        naked_graph.model_copy(update={"outfit_presets": with_presets.outfit_presets}),
        "combat_coat",
        in_structured_combat=False,
    )
    assert free_cost == 0
    assert set(restored.worn_items) == {"shirt_1", "mail_1", "coat_1"}

    # Putting on shirt (1) + mail (3) + coat (1) + dagger (1) = 6 actions in combat
    with pytest.raises(PermissionError):
        apply_outfit_preset(
            naked_graph.model_copy(update={"outfit_presets": with_presets.outfit_presets}),
            "combat_coat",
            in_structured_combat=True,
            available_action_budget=2,
        )

    equipped_in_combat, paid_cost = apply_outfit_preset(
        naked_graph.model_copy(update={"outfit_presets": with_presets.outfit_presets}),
        "combat_coat",
        in_structured_combat=True,
        available_action_budget=6,
    )
    assert paid_cost == 6
    assert unequip_node(equipped_in_combat, "waist").attachments == {}
