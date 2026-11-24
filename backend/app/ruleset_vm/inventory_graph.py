"""Universal Composable Container Graph & Layered Apparel/Equipment Engine (§1.1.3)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.ruleset_vm.ast_evaluator import evaluate_formula
from app.ruleset_vm.vm import EntityState

CapacityMode = Literal["weight", "slots", "grid_2d", "abstract_load", "unlimited"]
LayeringMode = Literal["abstract_slots", "anatomical_layered"]

DEFAULT_WEARABLE_LAYERS: tuple[str, ...] = (
    "base_undergarment",
    "inner_clothing",
    "mid_layer",
    "protective_armor",
    "outer_garment",
    "accessory_and_cosmetic",
)

DEFAULT_BODY_LOCATIONS: tuple[str, ...] = (
    "head",
    "face",
    "neck",
    "shoulders",
    "torso",
    "left_arm",
    "right_arm",
    "hands",
    "waist",
    "legs",
    "feet",
)


def _empty_str_int_dict() -> dict[str, int]:
    return {}


def _empty_str_str_dict() -> dict[str, str]:
    return {}


def _empty_parent_dict() -> dict[str, str | None]:
    return {}


def _empty_grid_dict() -> dict[str, GridPlacement]:
    return {}


def _empty_item_dict() -> dict[str, ItemNode]:
    return {}


def _empty_preset_dict() -> dict[str, OutfitPreset]:
    return {}


def _empty_aura_dict() -> dict[str, int | float]:
    return {}


class CapacityRule(BaseModel):
    """Capacity constraints for a root character inventory or nested container item."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: CapacityMode = "unlimited"
    max_weight: float | None = Field(default=None, ge=0.0)
    max_weight_formula: str | None = None
    max_slots: int | None = Field(default=None, ge=0)
    grid_width: int = Field(default=0, ge=0)
    grid_height: int = Field(default=0, ge=0)
    load_tiers: dict[str, int] = Field(default_factory=_empty_str_int_dict)
    selected_load_tier: str | None = None
    weightless_children: bool = False


class WearableLayerSpec(BaseModel):
    """Anatomical coverage and stacking semantics for clothing, cosmetics, gear, or armor."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    layer_id: str = Field(min_length=1)
    covered_locations: tuple[str, ...] = Field(min_length=1)
    conceals_inner_layers: bool = False
    appearance_tags: tuple[str, ...] = ()
    climate_tags: tuple[str, ...] = ()
    don_action_cost: int = Field(default=0, ge=0)
    doff_action_cost: int = Field(default=0, ge=0)
    mitigation_value: int | float = 0
    is_cosmetic_transmog: bool = False


class GridPlacement(BaseModel):
    """Top-left 2D cell coordinate inside a grid_2d container."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    x: int = Field(ge=0)
    y: int = Field(ge=0)
    rotated: bool = False


class ItemNode(BaseModel):
    """Unified item, wearable garment/armor, attachment, or container node."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    item_id: str = Field(min_length=1)
    template_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    quantity: int = Field(default=1, ge=1)
    unit_weight: float = Field(default=0.0, ge=0.0)
    slot_size: int = Field(default=1, ge=0)
    grid_width: int = Field(default=1, ge=1)
    grid_height: int = Field(default=1, ge=1)
    load_cost: int = Field(default=0, ge=0)
    attachable_nodes: tuple[str, ...] = ()
    wearable: WearableLayerSpec | None = None
    container_capacity: CapacityRule | None = None
    passive_aura_modifiers: dict[str, int | float] = Field(default_factory=_empty_aura_dict)
    aura_active_when: Literal["equipped", "carried"] = "equipped"
    granted_actions: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    concealable: bool = False


class OutfitPreset(BaseModel):
    """Saved named apparel and equipped loadout snapshot."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    preset_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    equipped_attachments: dict[str, str] = Field(default_factory=_empty_str_str_dict)
    worn_item_ids: tuple[str, ...] = ()


class AppearanceSnapshot(BaseModel):
    """Computed outermost visuals, diegetic concealment, climate tags, and localized armor."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    visible_by_location: dict[str, str]
    concealed_item_ids: tuple[str, ...]
    active_appearance_tags: tuple[str, ...]
    active_climate_tags: tuple[str, ...]
    location_mitigation: dict[str, int | float]


class InventoryGraphState(BaseModel):
    """Composable container graph plus universal anatomical apparel/equipment stacking."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    layering_mode: LayeringMode = "abstract_slots"
    layer_order: tuple[str, ...] = DEFAULT_WEARABLE_LAYERS
    body_locations: tuple[str, ...] = DEFAULT_BODY_LOCATIONS
    attachment_nodes: tuple[str, ...] = ("main_hand", "off_hand", "utility_1", "backpack")
    root_capacity: CapacityRule = Field(default_factory=CapacityRule)
    cosmetic_transmog_enabled: bool = False
    items: dict[str, ItemNode] = Field(default_factory=_empty_item_dict)
    parent_container: dict[str, str | None] = Field(default_factory=_empty_parent_dict)
    grid_placements: dict[str, GridPlacement] = Field(default_factory=_empty_grid_dict)
    attachments: dict[str, str] = Field(default_factory=_empty_str_str_dict)
    worn_items: tuple[str, ...] = ()
    transmog_overrides: dict[str, str] = Field(default_factory=_empty_str_str_dict)
    outfit_presets: dict[str, OutfitPreset] = Field(default_factory=_empty_preset_dict)


def _children_of(graph: InventoryGraphState, container_id: str | None) -> list[ItemNode]:
    return [
        graph.items[iid]
        for iid in sorted(graph.items)
        if graph.parent_container.get(iid) == container_id
    ]


def _subtree_weight(graph: InventoryGraphState, item: ItemNode) -> float:
    own = item.unit_weight * item.quantity
    if item.container_capacity is not None and item.container_capacity.weightless_children:
        return own
    nested = sum(_subtree_weight(graph, child) for child in _children_of(graph, item.item_id))
    return own + nested


def total_carried_weight(graph: InventoryGraphState, container_id: str | None = None) -> float:
    """Compute recursive weight inside a container or across the entire root inventory."""
    return sum(_subtree_weight(graph, child) for child in _children_of(graph, container_id))


def total_carried_slots(graph: InventoryGraphState, container_id: str | None = None) -> int:
    """Compute total slot consumption of direct children in a container or root."""
    return sum(child.slot_size * child.quantity for child in _children_of(graph, container_id))


def total_abstract_load(graph: InventoryGraphState) -> int:
    """Compute total abstract load points across all carried items."""
    return sum(item.load_cost * item.quantity for item in graph.items.values())


def _resolve_weight_limit(
    cap: CapacityRule, owner_ctx: Mapping[str, object] | None
) -> float | None:
    if cap.max_weight_formula is not None:
        raw = evaluate_formula(cap.max_weight_formula, owner_ctx or {})
        if isinstance(raw, (int, float)) and not isinstance(raw, bool):
            return float(raw)
        raise ValueError(f"max_weight_formula evaluated to non-numeric {raw!r}")
    return cap.max_weight


def _effective_footprint(item: ItemNode, placement: GridPlacement) -> tuple[int, int]:
    if placement.rotated:
        return item.grid_height, item.grid_width
    return item.grid_width, item.grid_height


def _grid_overlaps(
    ax: int,
    ay: int,
    aw: int,
    ah: int,
    bx: int,
    by: int,
    bw: int,
    bh: int,
) -> bool:
    return not (ax + aw <= bx or bx + bw <= ax or ay + ah <= by or by + bh <= ay)


def _find_or_validate_grid_pos(
    graph: InventoryGraphState,
    cap: CapacityRule,
    container_id: str | None,
    item: ItemNode,
    grid_pos: GridPlacement | None,
) -> GridPlacement:
    siblings = [
        child for child in _children_of(graph, container_id) if child.item_id != item.item_id
    ]
    occupied: list[tuple[int, int, int, int]] = []
    for sib in siblings:
        sib_pos = graph.grid_placements.get(sib.item_id)
        if sib_pos is not None:
            sw, sh = _effective_footprint(sib, sib_pos)
            occupied.append((sib_pos.x, sib_pos.y, sw, sh))

    def _fits_at(candidate: GridPlacement) -> bool:
        w, h = _effective_footprint(item, candidate)
        if candidate.x + w > cap.grid_width or candidate.y + h > cap.grid_height:
            return False
        return not any(
            _grid_overlaps(candidate.x, candidate.y, w, h, ox, oy, ow, oh)
            for ox, oy, ow, oh in occupied
        )

    if grid_pos is not None:
        if not _fits_at(grid_pos):
            raise ValueError(
                f"Item '{item.item_id}' does not fit at grid position ({grid_pos.x}, {grid_pos.y})."
            )
        return grid_pos

    for rotated in (False, True):
        for y in range(cap.grid_height):
            for x in range(cap.grid_width):
                candidate = GridPlacement(x=x, y=y, rotated=rotated)
                if _fits_at(candidate):
                    return candidate
    raise ValueError(f"No free 2D grid space remaining for '{item.item_id}'.")


def _validate_container_capacity(
    graph: InventoryGraphState,
    container_id: str | None,
    candidate_graph: InventoryGraphState,
    item: ItemNode,
    grid_pos: GridPlacement | None,
    owner_ctx: Mapping[str, object] | None,
) -> GridPlacement | None:
    if container_id is None:
        cap = candidate_graph.root_capacity
    else:
        container = candidate_graph.items.get(container_id)
        if container is None or container.container_capacity is None:
            raise ValueError(f"Target '{container_id}' is not a valid container.")
        cap = container.container_capacity

    if cap.mode == "weight":
        limit = _resolve_weight_limit(cap, owner_ctx)
        used = total_carried_weight(candidate_graph, container_id)
        if limit is not None and used > limit + 1e-9:
            raise ValueError(f"Weight capacity exceeded ({used:.2f} > {limit:.2f}).")
        return grid_pos

    if cap.mode == "slots":
        used_slots = total_carried_slots(candidate_graph, container_id)
        if cap.max_slots is not None and used_slots > cap.max_slots:
            raise ValueError(f"Slot capacity exceeded ({used_slots} > {cap.max_slots}).")
        return grid_pos

    if cap.mode == "grid_2d":
        return _find_or_validate_grid_pos(graph, cap, container_id, item, grid_pos)

    if cap.mode == "abstract_load":
        used_load = total_abstract_load(candidate_graph)
        limit = (
            cap.load_tiers.get(cap.selected_load_tier)
            if cap.selected_load_tier is not None
            else cap.max_slots
        )
        if limit is not None and used_load > limit:
            raise ValueError(f"Abstract load capacity exceeded ({used_load} > {limit}).")
        return grid_pos

    return grid_pos


def _enforce_ancestor_weight_limits(
    trial: InventoryGraphState,
    container_id: str | None,
    owner_ctx: Mapping[str, object] | None,
) -> None:
    if container_id is None:
        return
    ancestors: list[str | None] = []
    cursor: str | None = trial.parent_container.get(container_id)
    while True:
        ancestors.append(cursor)
        if cursor is None:
            break
        cursor = trial.parent_container.get(cursor)
    for anc_id in ancestors:
        anc_cap = (
            trial.root_capacity
            if anc_id is None
            else (trial.items[anc_id].container_capacity or CapacityRule())
        )
        if anc_cap.mode == "weight":
            limit = _resolve_weight_limit(anc_cap, owner_ctx)
            used = total_carried_weight(trial, anc_id)
            if limit is not None and used > limit + 1e-9:
                raise ValueError(f"Ancestor weight capacity exceeded ({used:.2f} > {limit:.2f}).")


def add_item(
    graph: InventoryGraphState,
    item: ItemNode,
    *,
    container_id: str | None = None,
    grid_pos: GridPlacement | None = None,
    owner_ctx: Mapping[str, object] | None = None,
) -> InventoryGraphState:
    """Add an item into root inventory or a sub-container while enforcing capacity rules."""
    if item.item_id in graph.items:
        raise ValueError(f"Duplicate item_id '{item.item_id}' in inventory.")
    if container_id is not None and container_id not in graph.items:
        raise KeyError(f"Unknown container_id '{container_id}'.")

    new_items = dict(graph.items)
    new_items[item.item_id] = item
    new_parents = dict(graph.parent_container)
    new_parents[item.item_id] = container_id
    trial = graph.model_copy(update={"items": new_items, "parent_container": new_parents})

    resolved_pos = _validate_container_capacity(
        graph, container_id, trial, item, grid_pos, owner_ctx
    )
    _enforce_ancestor_weight_limits(trial, container_id, owner_ctx)

    new_grid = dict(graph.grid_placements)
    if resolved_pos is not None:
        new_grid[item.item_id] = resolved_pos
    return trial.model_copy(update={"grid_placements": new_grid})


def _is_descendant(graph: InventoryGraphState, ancestor_id: str, candidate_id: str) -> bool:
    cursor: str | None = candidate_id
    while cursor is not None:
        if cursor == ancestor_id:
            return True
        cursor = graph.parent_container.get(cursor)
    return False


def move_item(
    graph: InventoryGraphState,
    item_id: str,
    target_container_id: str | None,
    *,
    grid_pos: GridPlacement | None = None,
    owner_ctx: Mapping[str, object] | None = None,
) -> InventoryGraphState:
    """Move an existing item between containers while preventing cycles and overflow."""
    if item_id not in graph.items:
        raise KeyError(f"Unknown item_id '{item_id}'.")
    if target_container_id is not None:
        if target_container_id not in graph.items:
            raise KeyError(f"Unknown target_container_id '{target_container_id}'.")
        if _is_descendant(graph, item_id, target_container_id):
            raise ValueError(
                f"Cannot move container '{item_id}' inside itself or descendant "
                f"'{target_container_id}'."
            )

    item = graph.items[item_id]
    new_parents = dict(graph.parent_container)
    new_parents[item_id] = target_container_id
    new_grid = dict(graph.grid_placements)
    new_grid.pop(item_id, None)

    stripped = graph.model_copy(
        update={"parent_container": new_parents, "grid_placements": new_grid}
    )
    resolved_pos = _validate_container_capacity(
        stripped, target_container_id, stripped, item, grid_pos, owner_ctx
    )
    _enforce_ancestor_weight_limits(stripped, target_container_id, owner_ctx)
    if resolved_pos is not None:
        new_grid[item_id] = resolved_pos
    return stripped.model_copy(update={"grid_placements": new_grid})


def remove_item(
    graph: InventoryGraphState,
    item_id: str,
    *,
    cascade: bool = False,
) -> InventoryGraphState:
    """Remove an item (optionally cascading into contained children) and clear equip bindings."""
    if item_id not in graph.items:
        raise KeyError(f"Unknown item_id '{item_id}'.")

    children = _children_of(graph, item_id)
    if children and not cascade:
        raise ValueError(
            f"Container '{item_id}' is non-empty; pass cascade=True to remove contents."
        )

    to_remove: set[str] = {item_id}
    if cascade:
        queue = [c.item_id for c in children]
        while queue:
            cid = queue.pop(0)
            to_remove.add(cid)
            queue.extend(grand.item_id for grand in _children_of(graph, cid))

    new_items = {k: v for k, v in graph.items.items() if k not in to_remove}
    new_parents = {k: v for k, v in graph.parent_container.items() if k not in to_remove}
    new_grid = {k: v for k, v in graph.grid_placements.items() if k not in to_remove}
    new_attach = {node: iid for node, iid in graph.attachments.items() if iid not in to_remove}
    new_worn = tuple(iid for iid in graph.worn_items if iid not in to_remove)
    new_transmog = {
        loc: iid for loc, iid in graph.transmog_overrides.items() if iid not in to_remove
    }
    return graph.model_copy(
        update={
            "items": new_items,
            "parent_container": new_parents,
            "grid_placements": new_grid,
            "attachments": new_attach,
            "worn_items": new_worn,
            "transmog_overrides": new_transmog,
        }
    )


def equip_to_node(graph: InventoryGraphState, item_id: str, node_id: str) -> InventoryGraphState:
    """Mount a carried item onto a named archetype AttachmentNode."""
    if item_id not in graph.items:
        raise KeyError(f"Unknown item_id '{item_id}'.")
    if node_id not in graph.attachment_nodes:
        raise ValueError(f"Unknown attachment node '{node_id}'.")
    item = graph.items[item_id]
    if item.attachable_nodes and node_id not in item.attachable_nodes:
        raise ValueError(f"Item '{item_id}' cannot attach to node '{node_id}'.")

    new_attach = {n: iid for n, iid in graph.attachments.items() if iid != item_id}
    new_attach[node_id] = item_id
    return graph.model_copy(update={"attachments": new_attach})


def unequip_node(graph: InventoryGraphState, node_id: str) -> InventoryGraphState:
    """Detach whichever item occupies node_id."""
    new_attach = dict(graph.attachments)
    new_attach.pop(node_id, None)
    return graph.model_copy(update={"attachments": new_attach})


def wear_item(graph: InventoryGraphState, item_id: str) -> InventoryGraphState:
    """Don clothing, cosmetic, disguise, gear, or armor onto its layer and body locations."""
    if item_id not in graph.items:
        raise KeyError(f"Unknown item_id '{item_id}'.")
    item = graph.items[item_id]
    if item.wearable is None:
        raise ValueError(f"Item '{item_id}' does not define a WearableLayerSpec.")
    spec = item.wearable
    if spec.is_cosmetic_transmog and not graph.cosmetic_transmog_enabled:
        raise PermissionError("Cosmetic transmog wearables are disabled by Campaign RAW policy.")
    if graph.layering_mode == "anatomical_layered":
        if spec.layer_id not in graph.layer_order:
            raise ValueError(f"Unknown wearable layer '{spec.layer_id}'.")
        for loc in spec.covered_locations:
            if loc not in graph.body_locations:
                raise ValueError(f"Unknown body location '{loc}'.")
        new_loc_set = set(spec.covered_locations)
        for existing_id in graph.worn_items:
            if existing_id == item_id:
                continue
            existing_spec = graph.items[existing_id].wearable
            if existing_spec is None or existing_spec.layer_id != spec.layer_id:
                continue
            overlap = new_loc_set & set(existing_spec.covered_locations)
            if overlap:
                raise ValueError(
                    f"Locations {sorted(overlap)} at layer '{spec.layer_id}' "
                    f"are already occupied by '{existing_id}'."
                )

    if item_id in graph.worn_items:
        return graph
    return graph.model_copy(update={"worn_items": (*graph.worn_items, item_id)})


def remove_worn_item(graph: InventoryGraphState, item_id: str) -> InventoryGraphState:
    """Doff a worn item back into inventory."""
    new_worn = tuple(iid for iid in graph.worn_items if iid != item_id)
    return graph.model_copy(update={"worn_items": new_worn})


def set_transmog_override(
    graph: InventoryGraphState,
    location: str,
    item_id: str | None,
) -> InventoryGraphState:
    """Set or clear a cosmetic transmog override when host policy enables transmog."""
    if not graph.cosmetic_transmog_enabled:
        raise PermissionError("Cosmetic transmog is disabled by default (Rules as Written).")
    if location not in graph.body_locations:
        raise ValueError(f"Unknown body location '{location}'.")
    updated = dict(graph.transmog_overrides)
    if item_id is None:
        updated.pop(location, None)
    else:
        if item_id not in graph.items:
            raise KeyError(f"Unknown item_id '{item_id}'.")
        updated[location] = item_id
    return graph.model_copy(update={"transmog_overrides": updated})


def save_outfit_preset(
    graph: InventoryGraphState,
    preset_id: str,
    label: str,
) -> InventoryGraphState:
    """Capture currently worn apparel and attachments into a named OutfitPreset."""
    presets = dict(graph.outfit_presets)
    presets[preset_id] = OutfitPreset(
        preset_id=preset_id,
        label=label,
        equipped_attachments=dict(graph.attachments),
        worn_item_ids=graph.worn_items,
    )
    return graph.model_copy(update={"outfit_presets": presets})


def apply_outfit_preset(
    graph: InventoryGraphState,
    preset_id: str,
    *,
    in_structured_combat: bool = False,
    available_action_budget: int | None = None,
) -> tuple[InventoryGraphState, int]:
    """Swap to a saved OutfitPreset, enforcing don/doff costs during structured combat."""
    preset = graph.outfit_presets.get(preset_id)
    if preset is None:
        raise KeyError(f"Unknown outfit preset '{preset_id}'.")

    for iid in preset.worn_item_ids:
        if iid not in graph.items:
            raise KeyError(f"Preset item '{iid}' is missing from inventory.")
    for node_id, iid in preset.equipped_attachments.items():
        if iid not in graph.items:
            raise KeyError(f"Preset attachment item '{iid}' is missing from inventory.")
        if node_id not in graph.attachment_nodes:
            raise ValueError(f"Preset attachment node '{node_id}' does not exist.")

    current_worn = set(graph.worn_items)
    target_worn = set(preset.worn_item_ids)
    to_doff = current_worn - target_worn
    to_don = target_worn - current_worn

    action_cost = 0
    if in_structured_combat:
        for iid in to_doff:
            spec = graph.items[iid].wearable
            if spec is not None:
                action_cost += spec.doff_action_cost
        for iid in to_don:
            spec = graph.items[iid].wearable
            if spec is not None:
                action_cost += spec.don_action_cost
        changed_nodes = {
            node
            for node in set(graph.attachments) | set(preset.equipped_attachments)
            if graph.attachments.get(node) != preset.equipped_attachments.get(node)
        }
        action_cost += len(changed_nodes)
        if available_action_budget is not None and action_cost > available_action_budget:
            raise PermissionError(
                f"Applying outfit '{preset_id}' in combat requires {action_cost} actions "
                f"(only {available_action_budget} available)."
            )

    swapped = graph.model_copy(
        update={"worn_items": (), "attachments": dict(preset.equipped_attachments)}
    )
    for iid in preset.worn_item_ids:
        swapped = wear_item(swapped, iid)
    return swapped, action_cost


def compute_visible_appearance(graph: InventoryGraphState) -> AppearanceSnapshot:
    """Resolve outermost visible layers, diegetic concealment, climate tags & armor totals."""
    layer_rank = {lid: idx for idx, lid in enumerate(graph.layer_order)}

    # Collect worn items ordered from outermost layer -> innermost
    worn_entries: list[tuple[int, ItemNode, WearableLayerSpec]] = []
    for iid in graph.worn_items:
        item = graph.items.get(iid)
        if item is not None and item.wearable is not None:
            rank = layer_rank.get(item.wearable.layer_id, 0)
            worn_entries.append((rank, item, item.wearable))
    worn_entries.sort(key=lambda entry: (-entry[0], entry[1].item_id))

    visible_by_loc: dict[str, str] = {}
    location_mitigation: dict[str, int | float] = {}
    climate_tags: set[str] = set()
    concealing_rank_by_loc: dict[str, int] = {}

    for rank, item, spec in worn_entries:
        climate_tags.update(spec.climate_tags)
        for loc in spec.covered_locations:
            if loc not in visible_by_loc:
                visible_by_loc[loc] = item.item_id
            location_mitigation[loc] = location_mitigation.get(loc, 0) + spec.mitigation_value
            if spec.conceals_inner_layers:
                prev_rank = concealing_rank_by_loc.get(loc, -1)
                if rank > prev_rank:
                    concealing_rank_by_loc[loc] = rank

    # Apply Host-enabled cosmetic transmog overrides on top of visual surface only
    if graph.cosmetic_transmog_enabled:
        for loc, override_id in graph.transmog_overrides.items():
            if override_id in graph.items:
                visible_by_loc[loc] = override_id

    # Conceal inner worn layers completely covered by outer conceals_inner_layers garments
    concealed: set[str] = set()
    for rank, item, spec in worn_entries:
        if all(concealing_rank_by_loc.get(loc, -1) > rank for loc in spec.covered_locations):
            concealed.add(item.item_id)

    # Conceal equipped concealable items when upper torso/waist is concealed by outer garment
    torso_or_waist_concealed = any(
        loc in concealing_rank_by_loc for loc in ("torso", "waist", "shoulders")
    )
    if torso_or_waist_concealed:
        for equipped_id in graph.attachments.values():
            eq_item = graph.items.get(equipped_id)
            if eq_item is not None and eq_item.concealable:
                concealed.add(eq_item.item_id)

    appearance_tags: set[str] = set()
    for item_id in set(visible_by_loc.values()):
        vis_item = graph.items.get(item_id)
        if vis_item is not None and vis_item.wearable is not None:
            appearance_tags.update(vis_item.wearable.appearance_tags)

    return AppearanceSnapshot(
        visible_by_location=visible_by_loc,
        concealed_item_ids=tuple(sorted(concealed)),
        active_appearance_tags=tuple(sorted(appearance_tags)),
        active_climate_tags=tuple(sorted(climate_tags)),
        location_mitigation=location_mitigation,
    )


def compute_active_auras(
    graph: InventoryGraphState,
) -> tuple[dict[str, int | float], tuple[str, ...]]:
    """Aggregate passive property modifier auras and granted actions from carried/equipped items."""
    equipped_ids = set(graph.attachments.values()) | set(graph.worn_items)
    modifiers: dict[str, int | float] = {}
    actions: set[str] = set()

    for item_id in sorted(graph.items):
        item = graph.items[item_id]
        if item.aura_active_when == "equipped" and item_id not in equipped_ids:
            continue
        for prop_key, delta in sorted(item.passive_aura_modifiers.items()):
            modifiers[prop_key] = modifiers.get(prop_key, 0) + delta
        actions.update(item.granted_actions)

    return modifiers, tuple(sorted(actions))


def sync_inventory_auras_to_entity(
    entity: EntityState,
    graph: InventoryGraphState,
) -> EntityState:
    """Return updated EntityState carrying active item passive auras & granted actions."""
    aura_mods, granted = compute_active_auras(graph)
    return entity.model_copy(
        update={
            "aura_modifiers": aura_mods,
            "granted_actions": granted,
        }
    )
