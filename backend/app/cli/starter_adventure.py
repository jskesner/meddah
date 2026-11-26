"""Agnostic 6-room starter adventure module ('The Sunken Crypt of Ashfall')."""

from __future__ import annotations

from app.cli.models import RoomNodeSpec
from app.ruleset_vm import (
    CapacityRule,
    EntityState,
    InventoryGraphState,
    ItemNode,
    RulesetSchema,
    ScalarValue,
    add_item,
)


def build_ashfall_rooms() -> dict[str, RoomNodeSpec]:
    """Return the 6-room Z0 <-> Z-1 starter graph for The Sunken Crypt of Ashfall."""
    rooms = (
        RoomNodeSpec(
            room_id="ashfall_courtyard",
            name="Ashfall Courtyard",
            floor_index=0,
            description=(
                "Weathered flagstone surrounds a moss-grown well beside the sinkhole stairs."
            ),
            exits={"south": "gatehouse_arch", "down": "sunken_vestibule"},
            npc_ids=("comp_vane",),
            prop_notes=("iron brazier", "sunken stairwell"),
        ),
        RoomNodeSpec(
            room_id="gatehouse_arch",
            name="Broken Gatehouse",
            floor_index=0,
            description=(
                "Rusted portcullis chains hang beside a carved lintel overlooking the yard."
            ),
            exits={"north": "ashfall_courtyard", "east": "watchtower_ruin"},
            npc_ids=(),
            prop_notes=("weathered notice board",),
        ),
        RoomNodeSpec(
            room_id="watchtower_ruin",
            name="Collapsed Watchtower",
            floor_index=0,
            description=(
                "Cold wind sweeps cracked battlements where a translucent scholar lingers."
            ),
            exits={"west": "gatehouse_arch"},
            npc_ids=("npc_archivist_shade",),
            prop_notes=("fallen astrolabe",),
        ),
        RoomNodeSpec(
            room_id="sunken_vestibule",
            name="Sunken Vestibule",
            floor_index=-1,
            description=(
                "Damp slate steps descend beneath the earth into a pillared ante-chamber."
            ),
            exits={
                "up": "ashfall_courtyard",
                "north": "ossuary_nave",
                "east": "scriptorium_alcove",
            },
            npc_ids=("npc_crypt_warden",),
            prop_notes=("sealed bronze urn", "hanging oil sconce"),
        ),
        RoomNodeSpec(
            room_id="scriptorium_alcove",
            name="Drowned Scriptorium",
            floor_index=-1,
            description=(
                "Stone lecterns jut above ink-dark puddles with copper canisters sealed in wax."
            ),
            exits={"west": "sunken_vestibule"},
            npc_ids=(),
            prop_notes=("wax-sealed canister",),
        ),
        RoomNodeSpec(
            room_id="ossuary_nave",
            name="Ossuary Nave",
            floor_index=-1,
            description=(
                "Vaulted ribs frame a central altar guarded by a rattling reliquary sentinel."
            ),
            exits={"south": "sunken_vestibule"},
            npc_ids=("npc_bone_sentinel",),
            prop_notes=("ash-covered altar",),
        ),
    )
    return {room.room_id: room for room in rooms}


def _baseline_maps_from_ruleset(
    ruleset: RulesetSchema,
    *,
    stat_offset: int = 0,
) -> tuple[dict[str, ScalarValue], dict[str, int]]:
    base_props: dict[str, ScalarValue] = {}
    for pid, pdef in sorted(ruleset.properties.items()):
        if pdef.formula is not None:
            continue
        default_val = pdef.default_value
        if isinstance(default_val, int) and not isinstance(default_val, bool):
            shifted = default_val + stat_offset
            if pdef.min_value is not None:
                shifted = max(int(pdef.min_value), shifted)
            if pdef.max_value is not None:
                shifted = min(int(pdef.max_value), shifted)
            base_props[pid] = shifted
        else:
            base_props[pid] = default_val

    base_pools: dict[str, int] = {}
    for pool_id, pool in sorted(ruleset.resource_pools.items()):
        if isinstance(pool.default_current, int) and not isinstance(pool.default_current, bool):
            base_pools[pool_id] = max(0, pool.default_current)
        else:
            base_pools[pool_id] = 10
    return base_props, base_pools


def bootstrap_entities_for_ruleset(
    ruleset: RulesetSchema,
    *,
    actor_name: str = "Traveler",
) -> tuple[list[EntityState], dict[str, InventoryGraphState]]:
    """Construct agnostic starter entities and inventories strictly from ruleset defaults."""
    lead_props, lead_pools = _baseline_maps_from_ruleset(ruleset, stat_offset=1)
    ally_props, ally_pools = _baseline_maps_from_ruleset(ruleset, stat_offset=0)
    foe_props, foe_pools = _baseline_maps_from_ruleset(ruleset, stat_offset=-1)
    # Give NPCs modest initial pool buffer when pools exist so multi-round actions succeed
    trimmed_foe_pools = {k: max(1, min(v, 8)) for k, v in foe_pools.items()}

    forms_list = tuple(sorted(ruleset.forms))

    entities = [
        EntityState(
            entity_id="pc_lead",
            name=actor_name,
            base_properties=lead_props,
            pools=lead_pools,
            available_forms=forms_list,
            is_player_controlled=True,
        ),
        EntityState(
            entity_id="comp_vane",
            name="Vane",
            base_properties=ally_props,
            pools=ally_pools,
            available_forms=forms_list,
            is_player_controlled=False,
        ),
        EntityState(
            entity_id="npc_archivist_shade",
            name="Archivist Shade",
            base_properties=ally_props,
            pools=trimmed_foe_pools,
            is_player_controlled=False,
        ),
        EntityState(
            entity_id="npc_crypt_warden",
            name="Crypt Warden",
            base_properties=foe_props,
            pools=trimmed_foe_pools,
            is_player_controlled=False,
        ),
        EntityState(
            entity_id="npc_bone_sentinel",
            name="Bone Sentinel",
            base_properties=foe_props,
            pools=trimmed_foe_pools,
            is_player_controlled=False,
        ),
    ]

    lead_inv = InventoryGraphState(root_capacity=CapacityRule(mode="unlimited"))
    lead_inv = add_item(
        lead_inv,
        ItemNode(
            item_id="ashfall_lantern",
            template_id="lantern",
            name="Brass Storm Lantern",
            tags=("light_source",),
        ),
    )
    lead_inv = add_item(
        lead_inv,
        ItemNode(
            item_id="brass_lockpicks",
            template_id="lockpicks",
            name="Fine Pickroll",
            concealable=True,
            slot_accessibility="concealed",
            tags=("tools",),
        ),
    )

    warden_inv = InventoryGraphState(root_capacity=CapacityRule(mode="unlimited"))
    warden_inv = add_item(
        warden_inv,
        ItemNode(
            item_id="crypt_vault_key",
            template_id="vault_key",
            name="Signet Vault Key",
            concealable=True,
            slot_accessibility="pouched",
            owner_entity_id="npc_crypt_warden",
            tags=("key",),
        ),
    )

    inventories: dict[str, InventoryGraphState] = {
        "pc_lead": lead_inv,
        "comp_vane": InventoryGraphState(root_capacity=CapacityRule(mode="unlimited")),
        "npc_archivist_shade": InventoryGraphState(root_capacity=CapacityRule(mode="unlimited")),
        "npc_crypt_warden": warden_inv,
        "npc_bone_sentinel": InventoryGraphState(root_capacity=CapacityRule(mode="unlimited")),
    }
    return entities, inventories
