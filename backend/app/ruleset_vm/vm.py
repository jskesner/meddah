"""Pure event-sourced Universal Ruleset Virtual Machine."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from app.ruleset_vm.ast_evaluator import FormulaError, ScalarValue, evaluate_formula
from app.ruleset_vm.blocks import (
    EffectSpec,
    FormBlock,
    FormPoolSpec,
    GearHandlingMode,
    OutcomeTier,
    RulesetSchema,
)
from app.ruleset_vm.flow_controller import FlowState, create_initial_flow
from app.ruleset_vm.randomizers import DeckRuntimeState, RollResult, resolve_randomizer
from app.ruleset_vm.reaction_window import (
    ReactionWindowState,
    open_reaction_window,
    resolve_reaction_timeout,
    submit_reaction_response,
)
from app.ruleset_vm.rng import RngStreamState, SceneRngRegistry

DEFAULT_MAX_HOOK_DEPTH = 4


class ActiveCondition(BaseModel):
    """Runtime status condition attached to an entity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    condition_id: str = Field(min_length=1)
    remaining_turns: int | None = None


class ActiveFormState(BaseModel):
    """Runtime state for an active alternate form or character transformation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    form_id: str = Field(min_length=1)
    remaining_turns: int | None = Field(default=None, ge=1)
    form_pools: dict[str, int] = Field(default_factory=dict)
    form_pool_maxes: dict[str, int] = Field(default_factory=dict)
    gear_handling: GearHandlingMode = "merge_into_form"
    previous_form_id: str | None = None
    involuntary: bool = False
    source_entity_id: str | None = None


class EntityState(BaseModel):
    """Authoritative event-sourced state of a single character, creature, or object."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    entity_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    base_properties: dict[str, ScalarValue] = Field(default_factory=dict)
    pools: dict[str, int] = Field(default_factory=dict)
    conditions: dict[str, ActiveCondition] = Field(default_factory=dict)
    tags: tuple[str, ...] = ()
    aura_modifiers: dict[str, int | float] = Field(default_factory=dict)
    granted_actions: tuple[str, ...] = ()
    available_forms: tuple[str, ...] = ()
    active_form: ActiveFormState | None = None


class ComputedEntityView(BaseModel):
    """Derived runtime view of an entity after forms, formulas, conditions & auras."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    entity_id: str
    name: str
    properties: dict[str, ScalarValue]
    pools: dict[str, int]
    pool_maxes: dict[str, int | None]
    conditions: tuple[str, ...]
    tags: tuple[str, ...]
    blocked_tags: tuple[str, ...]
    active_form_id: str | None = None
    active_form_involuntary: bool = False
    granted_actions: tuple[str, ...] = ()

    def to_eval_context(self) -> dict[str, object]:
        """Convert entity view into AST formula evaluation dict."""
        ctx: dict[str, object] = {
            "entity_id": self.entity_id,
            "name": self.name,
            "pools": dict(self.pools),
            "pool_maxes": dict(self.pool_maxes),
            "conditions": list(self.conditions),
            "tags": list(self.tags),
            "blocked_tags": list(self.blocked_tags),
            "active_form_id": self.active_form_id,
            "active_form_involuntary": self.active_form_involuntary,
            "granted_actions": list(self.granted_actions),
        }
        for prop_key, prop_val in self.properties.items():
            ctx[prop_key] = prop_val
        for pool_key, pool_val in self.pools.items():
            if pool_key not in ctx:
                ctx[pool_key] = pool_val
        return ctx


VmEventType = Literal[
    "ACTION_EXECUTED",
    "REACTION_OPENED",
    "REACTION_RESOLVED",
    "POOL_MODIFIED",
    "PROPERTY_SET",
    "CONDITION_CHANGED",
    "CLOCK_ADVANCED",
    "FLOW_UPDATED",
    "DECK_UPDATED",
    "RNG_ADVANCED",
    "CHARACTER_ADVANCED",
    "FORM_CHANGED",
    "SHEET_OVERRIDE",
    "MODULE_OVERRIDE",
    "MESSAGE_EMITTED",
]


class VmEvent(BaseModel):
    """Immutable append-only event record representing an atomic VM state transition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str = Field(min_length=1)
    event_type: VmEventType
    actor_id: str | None = None
    payload: dict[str, object] = Field(default_factory=dict)


class SceneState(BaseModel):
    """Complete deterministic scene state snapshot for replay and hash verification."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    scene_id: str = Field(min_length=1)
    entities: dict[str, EntityState] = Field(default_factory=dict)
    clocks: dict[str, int] = Field(default_factory=dict)
    flow: FlowState = Field(default_factory=FlowState)
    rng_streams: dict[str, RngStreamState] = Field(default_factory=dict)
    decks: dict[str, DeckRuntimeState] = Field(default_factory=dict)
    pending_reaction: ReactionWindowState | None = None
    active_modules: tuple[str, ...] = ()
    module_sub_options: dict[str, dict[str, str | bool | int]] = Field(default_factory=dict)
    log_messages: tuple[str, ...] = ()
    event_seq: int = Field(default=0, ge=0)


class ActionResolutionResult(BaseModel):
    """Outcome bundle returned when executing or resuming a VM action."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["executed", "pending_reaction", "manual_roll_required"]
    state: SceneState
    events: tuple[VmEvent, ...]
    roll_result: RollResult | None = None
    pending_window: ReactionWindowState | None = None


def _clamp_number(
    val: int | float,
    min_value: int | float | None,
    max_value: int | float | None,
) -> int | float:
    if min_value is not None and val < min_value:
        val = min_value
    if max_value is not None and val > max_value:
        val = max_value
    return val


def compute_entity_view(ruleset: RulesetSchema, entity: EntityState) -> ComputedEntityView:
    """Compute active forms, topological derived properties, condition modifiers, and auras."""
    active_form = entity.active_form
    form_def = ruleset.forms.get(active_form.form_id) if active_form is not None else None

    props: dict[str, ScalarValue] = {
        pid: prop.default_value for pid, prop in ruleset.properties.items()
    }
    if form_def is not None and form_def.property_mode == "replace_all":
        for k, v in form_def.property_values.items():
            props[k] = v
    else:
        for k, v in entity.base_properties.items():
            props[k] = v
        if form_def is not None and form_def.property_mode == "replace_subset":
            for k, v in form_def.property_values.items():
                props[k] = v

    cond_ids = tuple(sorted(entity.conditions))
    blocked_tags: set[str] = set()
    for cid in cond_ids:
        c_def = ruleset.conditions.get(cid)
        if c_def is not None:
            blocked_tags.update(c_def.blocks_tags)

    merged_tags_set = set(entity.tags)
    eff_actions = entity.granted_actions
    eff_pools = dict(entity.pools)

    if form_def is not None and active_form is not None:
        merged_tags_set.update(form_def.granted_tags)
        blocked_tags.update(form_def.blocked_tags)
        if form_def.action_mode == "replace":
            eff_actions = tuple(sorted(set(form_def.granted_actions)))
        else:
            eff_actions = tuple(sorted(set(entity.granted_actions) | set(form_def.granted_actions)))
        for pool_id, policy in sorted(form_def.pool_policies.items()):
            if policy.mode == "separate_form_pool":
                eff_pools[pool_id] = active_form.form_pools.get(pool_id, 0)
            elif policy.mode == "temp_bonus_pool":
                eff_pools[pool_id] = entity.pools.get(pool_id, 0) + active_form.form_pools.get(
                    pool_id, 0
                )

    merged_tags = tuple(sorted(merged_tags_set))
    effective_form_id = (
        active_form.form_id if (form_def is not None and active_form is not None) else None
    )
    active_form_involuntary = (
        bool(active_form.involuntary)
        if (form_def is not None and active_form is not None)
        else False
    )

    def _build_ctx(cur_props: dict[str, ScalarValue]) -> dict[str, object]:
        ctx: dict[str, object] = {
            "entity_id": entity.entity_id,
            "name": entity.name,
            "pools": dict(eff_pools),
            "conditions": list(cond_ids),
            "tags": list(merged_tags),
            "active_form_id": effective_form_id,
            "active_form_involuntary": active_form_involuntary,
        }
        ctx.update(cur_props)
        for pool_k, pool_v in eff_pools.items():
            if pool_k not in ctx:
                ctx[pool_k] = pool_v
        return ctx

    # Pre-Pass 1: apply form deltas targeting non-derived properties so derived stats reflect them
    if form_def is not None and form_def.property_deltas:
        pre_ctx = {"@self": _build_ctx(props)}
        for target_prop, delta_expr in sorted(form_def.property_deltas.items()):
            target_def = ruleset.properties.get(target_prop)
            if target_def is not None and target_def.formula is not None:
                continue
            delta_val = evaluate_formula(delta_expr, pre_ctx)
            if isinstance(delta_val, (int, float)) and not isinstance(delta_val, bool):
                existing = props.get(target_prop, 0)
                if isinstance(existing, (int, float)) and not isinstance(existing, bool):
                    props[target_prop] = existing + delta_val

    # Pass 1: derive properties in topological order
    for pid in ruleset.topological_property_order():
        prop_def = ruleset.properties[pid]
        if prop_def.formula is None:
            continue
        raw_val = evaluate_formula(prop_def.formula, {"@self": _build_ctx(props)})
        if isinstance(raw_val, (int, float)) and not isinstance(raw_val, bool):
            props[pid] = _clamp_number(raw_val, prop_def.min_value, prop_def.max_value)
        elif isinstance(raw_val, (bool, str)) or raw_val is None:
            props[pid] = raw_val

    # Pass 2: apply active condition modifiers, derived form deltas, and non-suppressed gear auras
    delta_ctx = {"@self": _build_ctx(props)}
    for cid in cond_ids:
        c_def = ruleset.conditions.get(cid)
        if c_def is None:
            continue
        for target_prop, delta_expr in sorted(c_def.property_modifiers.items()):
            delta_val = evaluate_formula(delta_expr, delta_ctx)
            if isinstance(delta_val, (int, float)) and not isinstance(delta_val, bool):
                existing = props.get(target_prop, 0)
                if isinstance(existing, (int, float)) and not isinstance(existing, bool):
                    props[target_prop] = existing + delta_val

    if form_def is not None:
        for target_prop, delta_expr in sorted(form_def.property_deltas.items()):
            target_def = ruleset.properties.get(target_prop)
            if target_def is None or target_def.formula is None:
                continue
            delta_val = evaluate_formula(delta_expr, delta_ctx)
            if isinstance(delta_val, (int, float)) and not isinstance(delta_val, bool):
                existing = props.get(target_prop, 0)
                if isinstance(existing, (int, float)) and not isinstance(existing, bool):
                    props[target_prop] = existing + delta_val

    if form_def is None or not form_def.suppress_gear_auras:
        for target_prop, aura_delta in sorted(entity.aura_modifiers.items()):
            existing = props.get(target_prop, 0)
            if isinstance(existing, (int, float)) and not isinstance(existing, bool):
                props[target_prop] = existing + aura_delta

    # Enforce min/max caps after modifiers
    for pid, prop_def in ruleset.properties.items():
        val = props.get(pid)
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            props[pid] = _clamp_number(val, prop_def.min_value, prop_def.max_value)

    final_ctx = {"@self": _build_ctx(props)}
    pool_maxes: dict[str, int | None] = {}
    for pool_id, pool_def in sorted(ruleset.resource_pools.items()):
        if pool_def.max_formula is None:
            pool_maxes[pool_id] = None
        else:
            raw_max = evaluate_formula(pool_def.max_formula, final_ctx)
            if isinstance(raw_max, (int, float)) and not isinstance(raw_max, bool):
                pool_maxes[pool_id] = int(raw_max)
            else:
                pool_maxes[pool_id] = None

    if form_def is not None and active_form is not None:
        for pool_id, policy in sorted(form_def.pool_policies.items()):
            if policy.mode == "separate_form_pool":
                if pool_id in active_form.form_pool_maxes:
                    pool_maxes[pool_id] = active_form.form_pool_maxes[pool_id]
            elif policy.mode == "temp_bonus_pool":
                base_max = pool_maxes.get(pool_id)
                bonus_max = active_form.form_pool_maxes.get(pool_id, 0)
                pool_maxes[pool_id] = (base_max + bonus_max) if base_max is not None else None

    return ComputedEntityView(
        entity_id=entity.entity_id,
        name=entity.name,
        properties=props,
        pools=eff_pools,
        pool_maxes=pool_maxes,
        conditions=cond_ids,
        tags=merged_tags,
        blocked_tags=tuple(sorted(blocked_tags)),
        active_form_id=effective_form_id,
        active_form_involuntary=active_form_involuntary,
        granted_actions=eff_actions,
    )


def build_active_form_state(
    ruleset: RulesetSchema,
    entity: EntityState,
    form: FormBlock,
    *,
    duration_override: int | None = None,
    involuntary: bool = False,
    source_entity_id: str | None = None,
) -> ActiveFormState:
    """Build ActiveFormState by evaluating pool policies against unshifted base state."""
    base_view = compute_entity_view(ruleset, entity.model_copy(update={"active_form": None}))
    form_eval_ctx: dict[str, object] = {"@self": base_view.to_eval_context()}

    form_pools: dict[str, int] = {}
    form_pool_maxes: dict[str, int] = {}
    for pool_id, policy in sorted(form.pool_policies.items()):
        if policy.mode == "shared_base_pool":
            continue
        init_val = max(
            0,
            _as_int_value(
                evaluate_formula(policy.initial_formula, form_eval_ctx),
                f"form_pool:{pool_id}",
            ),
        )
        if policy.max_formula is not None:
            max_val = max(
                0,
                _as_int_value(
                    evaluate_formula(policy.max_formula, form_eval_ctx),
                    f"form_pool_max:{pool_id}",
                ),
            )
            init_val = min(init_val, max_val)
            form_pool_maxes[pool_id] = max_val
        elif policy.mode in {"separate_form_pool", "temp_bonus_pool"}:
            form_pool_maxes[pool_id] = init_val
        form_pools[pool_id] = init_val

    previous_form_id = entity.active_form.form_id if entity.active_form else None
    remaining_turns = (
        duration_override if duration_override is not None else form.default_duration_turns
    )
    return ActiveFormState(
        form_id=form.form_id,
        remaining_turns=remaining_turns,
        form_pools=form_pools,
        form_pool_maxes=form_pool_maxes,
        gear_handling=form.gear_handling,
        previous_form_id=previous_form_id,
        involuntary=involuntary,
        source_entity_id=source_entity_id,
    )


def initialize_scene_state(
    ruleset: RulesetSchema,
    scene_id: str,
    entities: Sequence[EntityState] = (),
    *,
    scene_seed: str = "meddah-default-seed",
    active_modules: Sequence[str] = (),
) -> SceneState:
    """Create a deterministic initial SceneState with initialized pools, clocks, and RNG."""
    rng_reg = SceneRngRegistry(scene_seed)
    _ = rng_reg.stream("dice")
    entity_map: dict[str, EntityState] = {}

    for ent in entities:
        # Resolve default pools if omitted on EntityState
        view = compute_entity_view(ruleset, ent)
        resolved_pools = dict(ent.pools)
        eval_ctx = {"@self": view.to_eval_context()}
        for pool_id, pool_def in sorted(ruleset.resource_pools.items()):
            if pool_id not in resolved_pools:
                if isinstance(pool_def.default_current, int):
                    resolved_pools[pool_id] = pool_def.default_current
                else:
                    raw_cur = evaluate_formula(pool_def.default_current, eval_ctx)
                    resolved_pools[pool_id] = (
                        int(raw_cur) if isinstance(raw_cur, (int, float)) else 0
                    )
        entity_map[ent.entity_id] = ent.model_copy(update={"pools": resolved_pools})

    return SceneState(
        scene_id=scene_id,
        entities=entity_map,
        flow=create_initial_flow(ruleset.flow_config),
        rng_streams=rng_reg.snapshots(),
        active_modules=tuple(sorted(set(active_modules))),
    )


def state_hash(state: SceneState) -> str:
    """Compute canonical SHA-256 digest of SceneState for replay verification."""
    payload = state.model_dump(mode="json")
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _as_int_value(raw: object, label: str) -> int:
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise FormulaError("RPG-E1005", f"Expected integer/float for {label}, got {raw!r}")
    return int(raw)


def _as_scalar_value(raw: object, label: str) -> ScalarValue:
    if raw is None or isinstance(raw, (int, float, bool, str)):
        return raw
    raise FormulaError("RPG-E1005", f"Expected scalar value for {label}, got {raw!r}")


def apply_event(ruleset: RulesetSchema, state: SceneState, event: VmEvent) -> SceneState:
    """Pure state transition: apply(State_t, Event_{t+1}) -> State_{t+1}."""
    payload = event.payload
    next_seq = state.event_seq + 1

    if event.event_type == "POOL_MODIFIED":
        entity_id = str(payload["entity_id"])
        pool_id = str(payload["pool_id"])
        new_val = _as_int_value(payload["new_value"], "new_value")
        entity = state.entities[entity_id]
        updated_entities = dict(state.entities)
        if payload.get("pool_target") == "form" and entity.active_form is not None:
            updated_form_pools = dict(entity.active_form.form_pools)
            updated_form_pools[pool_id] = new_val
            next_form = entity.active_form.model_copy(update={"form_pools": updated_form_pools})
            updated_entities[entity_id] = entity.model_copy(update={"active_form": next_form})
        else:
            updated_pools = dict(entity.pools)
            updated_pools[pool_id] = new_val
            updated_entities[entity_id] = entity.model_copy(update={"pools": updated_pools})
        return state.model_copy(update={"entities": updated_entities, "event_seq": next_seq})

    if event.event_type == "PROPERTY_SET":
        entity_id = str(payload["entity_id"])
        prop_id = str(payload["prop_id"])
        new_scalar = _as_scalar_value(payload["new_value"], "new_value")
        entity = state.entities[entity_id]
        updated_props = dict(entity.base_properties)
        updated_props[prop_id] = new_scalar
        updated_entities = dict(state.entities)
        updated_entities[entity_id] = entity.model_copy(update={"base_properties": updated_props})
        return state.model_copy(update={"entities": updated_entities, "event_seq": next_seq})

    if event.event_type == "CONDITION_CHANGED":
        entity_id = str(payload["entity_id"])
        op = str(payload["op"])
        cond_id = str(payload["condition_id"])
        entity = state.entities[entity_id]
        updated_conds = dict(entity.conditions)
        if op == "add":
            dur_raw = payload.get("duration_turns")
            dur = int(dur_raw) if isinstance(dur_raw, int) else None
            updated_conds[cond_id] = ActiveCondition(condition_id=cond_id, remaining_turns=dur)
        elif op == "remove":
            updated_conds.pop(cond_id, None)
        updated_entities = dict(state.entities)
        updated_entities[entity_id] = entity.model_copy(update={"conditions": updated_conds})
        return state.model_copy(update={"entities": updated_entities, "event_seq": next_seq})

    if event.event_type == "CLOCK_ADVANCED":
        clock_id = str(payload["clock_id"])
        new_val = _as_int_value(payload["new_value"], "clock_new_value")
        updated_clocks = dict(state.clocks)
        updated_clocks[clock_id] = new_val
        return state.model_copy(update={"clocks": updated_clocks, "event_seq": next_seq})

    if event.event_type == "RNG_ADVANCED":
        stream_state = RngStreamState.model_validate(payload["stream_state"])
        updated_rng = dict(state.rng_streams)
        updated_rng[stream_state.stream_name] = stream_state
        return state.model_copy(update={"rng_streams": updated_rng, "event_seq": next_seq})

    if event.event_type == "DECK_UPDATED":
        deck_id = str(payload["deck_id"])
        deck_state = DeckRuntimeState.model_validate(payload["deck_state"])
        updated_decks = dict(state.decks)
        updated_decks[deck_id] = deck_state
        return state.model_copy(update={"decks": updated_decks, "event_seq": next_seq})

    if event.event_type == "FLOW_UPDATED":
        flow_state = FlowState.model_validate(payload["flow"])
        return state.model_copy(update={"flow": flow_state, "event_seq": next_seq})

    if event.event_type == "REACTION_OPENED":
        window = ReactionWindowState.model_validate(payload["window"])
        return state.model_copy(update={"pending_reaction": window, "event_seq": next_seq})

    if event.event_type == "REACTION_RESOLVED":
        return state.model_copy(update={"pending_reaction": None, "event_seq": next_seq})

    if event.event_type == "MESSAGE_EMITTED":
        msg = str(payload["message"])
        return state.model_copy(
            update={"log_messages": (*state.log_messages, msg), "event_seq": next_seq}
        )

    if event.event_type == "SHEET_OVERRIDE":
        entity_id = str(payload["entity_id"])
        entity = state.entities[entity_id]
        prop_overrides = payload.get("property_overrides", {})
        pool_overrides = payload.get("pool_overrides", {})
        updated_props = dict(entity.base_properties)
        if isinstance(prop_overrides, Mapping):
            prop_map = cast(Mapping[object, object], prop_overrides)
            for k, v in prop_map.items():
                updated_props[str(k)] = _as_scalar_value(v, f"override:{k}")
        updated_pools = dict(entity.pools)
        if isinstance(pool_overrides, Mapping):
            pool_map = cast(Mapping[object, object], pool_overrides)
            for k, v in pool_map.items():
                updated_pools[str(k)] = _as_int_value(v, f"pool_override:{k}")
        updated_conds = dict(entity.conditions)
        raw_add_conds = payload.get("add_conditions", {})
        if isinstance(raw_add_conds, Mapping):
            cond_map = cast(Mapping[object, object], raw_add_conds)
            for cid_obj, dur_obj in cond_map.items():
                cid = str(cid_obj)
                dur = (
                    int(dur_obj)
                    if isinstance(dur_obj, int) and not isinstance(dur_obj, bool)
                    else None
                )
                updated_conds[cid] = ActiveCondition(condition_id=cid, remaining_turns=dur)
        raw_rem_conds = payload.get("remove_conditions", ())
        if isinstance(raw_rem_conds, Sequence) and not isinstance(raw_rem_conds, str):
            for cid_obj in cast(Sequence[object], raw_rem_conds):
                updated_conds.pop(str(cid_obj), None)
        updated_tags = set(entity.tags)
        raw_add_tags = payload.get("add_tags", ())
        if isinstance(raw_add_tags, Sequence) and not isinstance(raw_add_tags, str):
            for tag_obj in cast(Sequence[object], raw_add_tags):
                updated_tags.add(str(tag_obj))
        raw_rem_tags = payload.get("remove_tags", ())
        if isinstance(raw_rem_tags, Sequence) and not isinstance(raw_rem_tags, str):
            for tag_obj in cast(Sequence[object], raw_rem_tags):
                updated_tags.discard(str(tag_obj))
        updated_entities = dict(state.entities)
        updated_entities[entity_id] = entity.model_copy(
            update={
                "base_properties": updated_props,
                "pools": updated_pools,
                "conditions": updated_conds,
                "tags": tuple(sorted(updated_tags)),
            }
        )
        return state.model_copy(update={"entities": updated_entities, "event_seq": next_seq})

    if event.event_type == "CHARACTER_ADVANCED":
        entity_id = str(payload["entity_id"])
        entity = state.entities[entity_id]
        updated_props = dict(entity.base_properties)
        raw_prop_up = payload.get("property_updates", {})
        if isinstance(raw_prop_up, Mapping):
            prop_map = cast(Mapping[object, object], raw_prop_up)
            for k, v in prop_map.items():
                updated_props[str(k)] = _as_scalar_value(v, f"advance:{k}")
        updated_pools = dict(entity.pools)
        raw_pool_up = payload.get("pool_updates", {})
        if isinstance(raw_pool_up, Mapping):
            pool_map = cast(Mapping[object, object], raw_pool_up)
            for k, v in pool_map.items():
                updated_pools[str(k)] = _as_int_value(v, f"advance_pool:{k}")
        tags_set = set(entity.tags)
        raw_added_tags = payload.get("added_tags", ())
        if isinstance(raw_added_tags, Sequence) and not isinstance(raw_added_tags, str):
            for tag_item in cast(Sequence[object], raw_added_tags):
                tags_set.add(str(tag_item))
        raw_removed_tags = payload.get("removed_tags", ())
        if isinstance(raw_removed_tags, Sequence) and not isinstance(raw_removed_tags, str):
            for tag_item in cast(Sequence[object], raw_removed_tags):
                tags_set.discard(str(tag_item))
        actions_set = set(entity.granted_actions)
        raw_actions = payload.get("added_actions", ())
        if isinstance(raw_actions, Sequence) and not isinstance(raw_actions, str):
            for act_item in cast(Sequence[object], raw_actions):
                actions_set.add(str(act_item))
        updated_entities = dict(state.entities)
        updated_entities[entity_id] = entity.model_copy(
            update={
                "base_properties": updated_props,
                "pools": updated_pools,
                "tags": tuple(sorted(tags_set)),
                "granted_actions": tuple(sorted(actions_set)),
            }
        )
        return state.model_copy(update={"entities": updated_entities, "event_seq": next_seq})

    if event.event_type == "MODULE_OVERRIDE":
        mod_id = str(payload["module_id"])
        enabled = bool(payload["enabled"])
        current = set(state.active_modules)
        if enabled:
            current.add(mod_id)
        else:
            current.discard(mod_id)
        sub_opts = {k: dict(v) for k, v in state.module_sub_options.items()}
        raw_sub_entry = payload.get("sub_options")
        if isinstance(raw_sub_entry, Mapping):
            sub_map = cast(Mapping[object, object], raw_sub_entry)
            raw_sub: dict[str, str | bool | int] = {}
            for sk, sv in sub_map.items():
                if isinstance(sv, (str, bool, int)):
                    raw_sub[str(sk)] = sv
            sub_opts[mod_id] = raw_sub
        return state.model_copy(
            update={
                "active_modules": tuple(sorted(current)),
                "module_sub_options": sub_opts,
                "event_seq": next_seq,
            }
        )

    if event.event_type == "FORM_CHANGED":
        entity_id = str(payload["entity_id"])
        op = str(payload["op"])
        entity = state.entities[entity_id]
        updated_entities = dict(state.entities)
        if op == "shift":
            next_form = ActiveFormState.model_validate(payload["active_form"])
            updated_entities[entity_id] = entity.model_copy(update={"active_form": next_form})
        elif op == "revert":
            updated_entities[entity_id] = entity.model_copy(update={"active_form": None})
        elif op == "tick" and entity.active_form is not None:
            rem_raw = payload.get("remaining_turns")
            if isinstance(rem_raw, int) and not isinstance(rem_raw, bool) and rem_raw > 0:
                next_form = entity.active_form.model_copy(update={"remaining_turns": rem_raw})
                updated_entities[entity_id] = entity.model_copy(update={"active_form": next_form})
            else:
                updated_entities[entity_id] = entity.model_copy(update={"active_form": None})
        return state.model_copy(update={"entities": updated_entities, "event_seq": next_seq})

    # ACTION_EXECUTED serves as an immutable audit marker in the event stream
    _ = ruleset
    return state.model_copy(update={"event_seq": next_seq})


def replay_events(
    ruleset: RulesetSchema,
    initial_state: SceneState,
    events: Sequence[VmEvent],
) -> SceneState:
    """Deterministically reconstruct SceneState by folding all recorded VmEvents."""
    current = initial_state
    for evt in events:
        current = apply_event(ruleset, current, evt)
    return current


def _next_event_id(state: SceneState, offset: int) -> str:
    return f"evt_{state.scene_id}_{state.event_seq + offset + 1:06d}"


def _apply_base_pool_delta(
    ruleset: RulesetSchema,
    state: SceneState,
    *,
    scope_entity_id: str,
    pool_id: str,
    delta: int,
    actor_id: str,
    pending_events: list[VmEvent],
) -> SceneState:
    ent = state.entities[scope_entity_id]
    pool_def = ruleset.resource_pools.get(pool_id)
    min_val = pool_def.min_value if pool_def is not None else 0
    base_view = compute_entity_view(ruleset, ent.model_copy(update={"active_form": None}))
    max_val = base_view.pool_maxes.get(pool_id)
    new_val = ent.pools.get(pool_id, 0) + delta
    if new_val < min_val:
        new_val = min_val
    if max_val is not None and new_val > max_val:
        new_val = max_val
    evt = VmEvent(
        event_id=_next_event_id(state, 0),
        event_type="POOL_MODIFIED",
        actor_id=actor_id,
        payload={
            "entity_id": scope_entity_id,
            "pool_id": pool_id,
            "delta": delta,
            "new_value": new_val,
        },
    )
    pending_events.append(evt)
    return apply_event(ruleset, state, evt)


def _emit_form_revert_event(
    ruleset: RulesetSchema,
    state: SceneState,
    *,
    scope_entity_id: str,
    form_id: str,
    reason: str,
    forced: bool,
    actor_id: str,
    pending_events: list[VmEvent],
) -> SceneState:
    rev_evt = VmEvent(
        event_id=_next_event_id(state, 0),
        event_type="FORM_CHANGED",
        actor_id=actor_id,
        payload={
            "entity_id": scope_entity_id,
            "op": "revert",
            "form_id": form_id,
            "reason": reason,
            "forced": forced,
        },
    )
    pending_events.append(rev_evt)
    return apply_event(ruleset, state, rev_evt)


def _fire_form_reverted_hooks(
    ruleset: RulesetSchema,
    state: SceneState,
    *,
    scope_entity_id: str,
    prev_form: ActiveFormState,
    reason: str,
    forced: bool,
    emitted: list[VmEvent],
    hook_depth: int,
) -> SceneState:
    return _fire_event_hooks(
        ruleset,
        state,
        event_name="on_form_reverted",
        actor_id=scope_entity_id,
        target_id=None,
        event_data={
            "entity_id": scope_entity_id,
            "form_id": prev_form.form_id,
            "reason": reason,
            "forced": forced,
            "was_involuntary": prev_form.involuntary,
            "source_entity_id": prev_form.source_entity_id,
        },
        emitted=emitted,
        hook_depth=hook_depth,
    )


def _resolve_effect_events(
    ruleset: RulesetSchema,
    state: SceneState,
    effect: EffectSpec,
    *,
    actor_id: str | None,
    target_id: str | None,
    eval_ctx: dict[str, object],
    pending_events: list[VmEvent],
    hook_depth: int = 0,
) -> SceneState:
    """Compile a declarative EffectSpec into deterministic VmEvents and apply them."""
    scope_entity_id: str | None = None
    if effect.target_scope == "self":
        scope_entity_id = actor_id
    elif effect.target_scope == "target":
        scope_entity_id = target_id if target_id is not None else actor_id
    event_actor = actor_id or "system"

    if effect.kind == "modify_pool":
        if scope_entity_id is None or scope_entity_id not in state.entities:
            return state
        delta = _as_int_value(evaluate_formula(effect.formula, eval_ctx), "modify_pool delta")
        ent = state.entities[scope_entity_id]
        form_def = ruleset.forms.get(ent.active_form.form_id) if ent.active_form else None
        policy: FormPoolSpec | None = (
            form_def.pool_policies.get(effect.target_key)
            if (form_def is not None and ent.active_form is not None)
            else None
        )

        if policy is not None and ent.active_form is not None:
            if policy.mode == "separate_form_pool":
                cur_form = ent.active_form.form_pools.get(effect.target_key, 0)
                form_max = ent.active_form.form_pool_maxes.get(effect.target_key)
                raw_after = cur_form + delta
                clamped_form = max(0, raw_after)
                if form_max is not None and clamped_form > form_max:
                    clamped_form = form_max

                form_evt = VmEvent(
                    event_id=_next_event_id(state, 0),
                    event_type="POOL_MODIFIED",
                    actor_id=event_actor,
                    payload={
                        "entity_id": scope_entity_id,
                        "pool_id": effect.target_key,
                        "pool_target": "form",
                        "delta": delta if raw_after >= 0 else -cur_form,
                        "new_value": clamped_form,
                    },
                )
                pending_events.append(form_evt)
                cur_state = apply_event(ruleset, state, form_evt)

                reverted_form: ActiveFormState | None = None
                if raw_after <= 0 and delta < 0 and policy.auto_revert_on_zero:
                    reverted_form = ent.active_form
                    cur_state = _emit_form_revert_event(
                        ruleset,
                        cur_state,
                        scope_entity_id=scope_entity_id,
                        form_id=reverted_form.form_id,
                        reason="form_pool_depleted",
                        forced=True,
                        actor_id=event_actor,
                        pending_events=pending_events,
                    )

                if raw_after < 0 and policy.overflow_to_base:
                    cur_state = _apply_base_pool_delta(
                        ruleset,
                        cur_state,
                        scope_entity_id=scope_entity_id,
                        pool_id=effect.target_key,
                        delta=raw_after,
                        actor_id=event_actor,
                        pending_events=pending_events,
                    )

                if reverted_form is not None:
                    cur_state = _fire_form_reverted_hooks(
                        ruleset,
                        cur_state,
                        scope_entity_id=scope_entity_id,
                        prev_form=reverted_form,
                        reason="form_pool_depleted",
                        forced=True,
                        emitted=pending_events,
                        hook_depth=hook_depth + 1,
                    )
                return cur_state

            if policy.mode == "temp_bonus_pool" and delta < 0:
                cur_state = state
                cur_bonus = ent.active_form.form_pools.get(effect.target_key, 0)
                rem_delta = delta
                reverted_form = None
                if cur_bonus > 0:
                    absorbed = min(cur_bonus, abs(delta))
                    new_bonus = cur_bonus - absorbed
                    rem_delta = delta + absorbed
                    bonus_evt = VmEvent(
                        event_id=_next_event_id(cur_state, 0),
                        event_type="POOL_MODIFIED",
                        actor_id=event_actor,
                        payload={
                            "entity_id": scope_entity_id,
                            "pool_id": effect.target_key,
                            "pool_target": "form",
                            "delta": -absorbed,
                            "new_value": new_bonus,
                        },
                    )
                    pending_events.append(bonus_evt)
                    cur_state = apply_event(ruleset, cur_state, bonus_evt)
                    if new_bonus <= 0 and policy.auto_revert_on_zero:
                        reverted_form = ent.active_form
                        cur_state = _emit_form_revert_event(
                            ruleset,
                            cur_state,
                            scope_entity_id=scope_entity_id,
                            form_id=reverted_form.form_id,
                            reason="form_pool_depleted",
                            forced=True,
                            actor_id=event_actor,
                            pending_events=pending_events,
                        )
                if rem_delta < 0 and policy.overflow_to_base:
                    cur_state = _apply_base_pool_delta(
                        ruleset,
                        cur_state,
                        scope_entity_id=scope_entity_id,
                        pool_id=effect.target_key,
                        delta=rem_delta,
                        actor_id=event_actor,
                        pending_events=pending_events,
                    )
                if reverted_form is not None:
                    cur_state = _fire_form_reverted_hooks(
                        ruleset,
                        cur_state,
                        scope_entity_id=scope_entity_id,
                        prev_form=reverted_form,
                        reason="form_pool_depleted",
                        forced=True,
                        emitted=pending_events,
                        hook_depth=hook_depth + 1,
                    )
                return cur_state

        return _apply_base_pool_delta(
            ruleset,
            state,
            scope_entity_id=scope_entity_id,
            pool_id=effect.target_key,
            delta=delta,
            actor_id=event_actor,
            pending_events=pending_events,
        )

    if effect.kind == "set_property":
        if scope_entity_id is None or scope_entity_id not in state.entities:
            return state
        new_val = _as_scalar_value(evaluate_formula(effect.formula, eval_ctx), "set_property value")
        evt = VmEvent(
            event_id=_next_event_id(state, 0),
            event_type="PROPERTY_SET",
            actor_id=event_actor,
            payload={
                "entity_id": scope_entity_id,
                "prop_id": effect.target_key,
                "new_value": new_val,
            },
        )
        pending_events.append(evt)
        return apply_event(ruleset, state, evt)

    if effect.kind in {"add_condition", "remove_condition"}:
        if scope_entity_id is None or scope_entity_id not in state.entities:
            return state
        op = "add" if effect.kind == "add_condition" else "remove"
        cond_def = ruleset.conditions.get(effect.target_key)
        duration = (
            effect.duration_turns
            if effect.duration_turns is not None
            else (cond_def.default_duration_turns if cond_def else None)
        )
        evt = VmEvent(
            event_id=_next_event_id(state, 0),
            event_type="CONDITION_CHANGED",
            actor_id=event_actor,
            payload={
                "entity_id": scope_entity_id,
                "op": op,
                "condition_id": effect.target_key,
                "duration_turns": duration,
            },
        )
        pending_events.append(evt)
        cur_state = apply_event(ruleset, state, evt)
        return _fire_event_hooks(
            ruleset,
            cur_state,
            event_name="on_condition_changed",
            actor_id=scope_entity_id,
            target_id=None,
            event_data={
                "entity_id": scope_entity_id,
                "op": op,
                "condition_id": effect.target_key,
                "duration_turns": duration,
                "source_entity_id": actor_id,
            },
            emitted=pending_events,
            hook_depth=hook_depth + 1,
        )

    if effect.kind == "shift_form":
        if scope_entity_id is None or scope_entity_id not in state.entities:
            return state
        form = ruleset.forms.get(effect.target_key)
        if form is None:
            return state
        target_ent = state.entities[scope_entity_id]
        if not effect.forced:
            target_view = compute_entity_view(ruleset, target_ent)
            if not bool(evaluate_formula(form.requires, {"@self": target_view.to_eval_context()})):
                return state
        prev_form_id = target_ent.active_form.form_id if target_ent.active_form else None
        next_form = build_active_form_state(
            ruleset,
            target_ent,
            form,
            duration_override=effect.duration_turns,
            involuntary=effect.forced,
            source_entity_id=actor_id,
        )
        shift_evt = VmEvent(
            event_id=_next_event_id(state, 0),
            event_type="FORM_CHANGED",
            actor_id=event_actor,
            payload={
                "entity_id": scope_entity_id,
                "op": "shift",
                "form_id": form.form_id,
                "previous_form_id": prev_form_id,
                "gear_handling": form.gear_handling,
                "involuntary": effect.forced,
                "source_entity_id": actor_id,
                "active_form": next_form.model_dump(mode="json"),
            },
        )
        pending_events.append(shift_evt)
        cur_state = apply_event(ruleset, state, shift_evt)
        return _fire_event_hooks(
            ruleset,
            cur_state,
            event_name="on_form_entered",
            actor_id=scope_entity_id,
            target_id=None,
            event_data={
                "entity_id": scope_entity_id,
                "form_id": form.form_id,
                "previous_form_id": prev_form_id,
                "involuntary": effect.forced,
                "source_entity_id": actor_id,
            },
            emitted=pending_events,
            hook_depth=hook_depth + 1,
        )

    if effect.kind == "revert_form":
        if scope_entity_id is None or scope_entity_id not in state.entities:
            return state
        target_ent = state.entities[scope_entity_id]
        if target_ent.active_form is None:
            return state
        prev_form = target_ent.active_form
        if effect.target_key and prev_form.form_id != effect.target_key:
            return state
        if prev_form.involuntary and not effect.forced:
            return state
        reason = effect.formula if effect.formula and effect.formula != "0" else "effect_revert"
        cur_state = _emit_form_revert_event(
            ruleset,
            state,
            scope_entity_id=scope_entity_id,
            form_id=prev_form.form_id,
            reason=reason,
            forced=effect.forced,
            actor_id=event_actor,
            pending_events=pending_events,
        )
        return _fire_form_reverted_hooks(
            ruleset,
            cur_state,
            scope_entity_id=scope_entity_id,
            prev_form=prev_form,
            reason=reason,
            forced=effect.forced,
            emitted=pending_events,
            hook_depth=hook_depth + 1,
        )

    if effect.kind == "advance_clock":
        delta = _as_int_value(evaluate_formula(effect.formula, eval_ctx), "clock delta")
        new_val = max(0, state.clocks.get(effect.target_key, 0) + delta)
        evt = VmEvent(
            event_id=_next_event_id(state, 0),
            event_type="CLOCK_ADVANCED",
            actor_id=event_actor,
            payload={
                "clock_id": effect.target_key,
                "delta": delta,
                "new_value": new_val,
            },
        )
        pending_events.append(evt)
        return apply_event(ruleset, state, evt)

    evt = VmEvent(
        event_id=_next_event_id(state, 0),
        event_type="MESSAGE_EMITTED",
        actor_id=event_actor,
        payload={"message": effect.formula},
    )
    pending_events.append(evt)
    return apply_event(ruleset, state, evt)


def _fire_event_hooks(
    ruleset: RulesetSchema,
    state: SceneState,
    *,
    event_name: str,
    actor_id: str | None,
    target_id: str | None,
    event_data: Mapping[str, object],
    emitted: list[VmEvent],
    hook_depth: int = 0,
) -> SceneState:
    if hook_depth > DEFAULT_MAX_HOOK_DEPTH:
        return state
    cur_state = state
    for hook_id in sorted(ruleset.event_hooks):
        hook = ruleset.event_hooks[hook_id]
        if hook.event_name != event_name:
            continue
        actor_view = (
            compute_entity_view(ruleset, cur_state.entities[actor_id])
            if actor_id is not None and actor_id in cur_state.entities
            else None
        )
        target_view = (
            compute_entity_view(ruleset, cur_state.entities[target_id])
            if target_id is not None and target_id in cur_state.entities
            else None
        )
        ctx: dict[str, object] = {
            "@self": actor_view.to_eval_context() if actor_view is not None else None,
            "@target": target_view.to_eval_context() if target_view is not None else None,
            "@event": dict(event_data),
        }
        if bool(evaluate_formula(hook.condition, ctx)):
            for eff in hook.effects:
                cur_state = _resolve_effect_events(
                    ruleset,
                    cur_state,
                    eff,
                    actor_id=actor_id,
                    target_id=target_id,
                    eval_ctx=ctx,
                    pending_events=emitted,
                    hook_depth=hook_depth,
                )
    return cur_state


def trigger_event_hooks(
    ruleset: RulesetSchema,
    state: SceneState,
    *,
    event_name: str,
    actor_id: str | None = None,
    target_id: str | None = None,
    event_data: Mapping[str, object] | None = None,
    broadcast_to_entities: bool = False,
) -> tuple[SceneState, tuple[VmEvent, ...]]:
    """Dispatch declarative EventHookBlocks for scene or entity lifecycle events."""
    if broadcast_to_entities and actor_id is not None:
        raise ValueError("broadcast_to_entities=True cannot be combined with an explicit actor_id.")
    if actor_id is not None and actor_id not in state.entities:
        raise KeyError(f"Unknown actor entity '{actor_id}'")
    if target_id is not None and target_id not in state.entities:
        raise KeyError(f"Unknown target entity '{target_id}'")

    data = dict(event_data or {})
    emitted: list[VmEvent] = []
    cur_state = state

    if broadcast_to_entities:
        for eid in sorted(state.entities):
            cur_state = _fire_event_hooks(
                ruleset,
                cur_state,
                event_name=event_name,
                actor_id=eid,
                target_id=target_id,
                event_data=data,
                emitted=emitted,
                hook_depth=0,
            )
    else:
        cur_state = _fire_event_hooks(
            ruleset,
            cur_state,
            event_name=event_name,
            actor_id=actor_id,
            target_id=target_id,
            event_data=data,
            emitted=emitted,
            hook_depth=0,
        )
    return cur_state, tuple(emitted)


def execute_action(
    ruleset: RulesetSchema,
    state: SceneState,
    actor_id: str,
    action_id: str,
    *,
    target_id: str | None = None,
    manual_roll_mode: bool = False,
    wager_bonus: int | float = 0,
    bypass_reactions: bool = False,
) -> ActionResolutionResult:
    """Validate and execute a Ruleset ActionBlock through preconditions, costs, rolls & hooks."""
    if actor_id not in state.entities:
        raise KeyError(f"Unknown actor entity '{actor_id}'")
    action = ruleset.actions.get(action_id)
    if action is None:
        raise KeyError(f"Unknown ruleset action '{action_id}'")
    if action.requires_target and (target_id is None or target_id not in state.entities):
        raise ValueError(f"Action '{action_id}' requires a valid target_id.")
    if target_id is not None and target_id not in state.entities:
        raise KeyError(f"Unknown target entity '{target_id}'")

    actor_view = compute_entity_view(ruleset, state.entities[actor_id])
    if set(action.tags) & set(actor_view.blocked_tags):
        raise PermissionError(
            f"Action '{action_id}' is gated/blocked by active conditions on '{actor_id}'."
        )

    target_view = (
        compute_entity_view(ruleset, state.entities[target_id]) if target_id is not None else None
    )
    eval_ctx: dict[str, object] = {
        "@self": actor_view.to_eval_context(),
        "@target": target_view.to_eval_context() if target_view else None,
    }
    if not bool(evaluate_formula(action.requires, eval_ctx)):
        raise ValueError(f"Precondition failed for action '{action_id}'.")

    # Verify resource pool costs up front
    actor_entity = state.entities[actor_id]
    pool_deltas: dict[str, tuple[int, int]] = {}
    for pool_id, cost_expr in sorted(action.pool_costs.items()):
        cost_val = _as_int_value(evaluate_formula(cost_expr, eval_ctx), f"cost:{pool_id}")
        current_pool = actor_entity.pools.get(pool_id, 0)
        if current_pool < cost_val:
            raise ValueError(
                f"Insufficient pool '{pool_id}' ({current_pool} < {cost_val}) for '{action_id}'."
            )
        pool_deltas[pool_id] = (cost_val, current_pool - cost_val)

    # Check Explicit Reaction Window before resolving action
    if action.allow_reactions and not bypass_reactions and target_id is not None:
        views_map = {
            eid: compute_entity_view(ruleset, ent).to_eval_context()
            for eid, ent in state.entities.items()
        }
        pools_map = {eid: ent.pools for eid, ent in state.entities.items()}
        window = open_reaction_window(
            window_id=f"react_{state.scene_id}_{state.event_seq + 1:06d}",
            pending_action_id=action_id,
            actor_id=actor_id,
            target_ids=[target_id],
            ruleset=ruleset,
            entity_views=views_map,
            entity_pools=pools_map,
            manual_roll_mode=manual_roll_mode,
            wager_bonus=wager_bonus,
        )
        if window is not None:
            evt = VmEvent(
                event_id=_next_event_id(state, 0),
                event_type="REACTION_OPENED",
                actor_id=actor_id,
                payload={"window": window.model_dump(mode="json")},
            )
            next_state = apply_event(ruleset, state, evt)
            return ActionResolutionResult(
                status="pending_reaction",
                state=next_state,
                events=(evt,),
                pending_window=window,
            )

    if manual_roll_mode and action.resolution_id is not None:
        return ActionResolutionResult(
            status="manual_roll_required",
            state=state,
            events=(),
        )

    emitted: list[VmEvent] = []
    cur_state = state

    # Deduct pool costs
    for pool_id, (cost_val, new_pool_val) in sorted(pool_deltas.items()):
        evt = VmEvent(
            event_id=_next_event_id(cur_state, 0),
            event_type="POOL_MODIFIED",
            actor_id=actor_id,
            payload={
                "entity_id": actor_id,
                "pool_id": pool_id,
                "delta": -cost_val,
                "new_value": new_pool_val,
            },
        )
        emitted.append(evt)
        cur_state = apply_event(ruleset, cur_state, evt)

    # Resolve randomizer if resolution_id is set
    roll_result: RollResult | None = None
    matched_tier: OutcomeTier | None = None
    if action.resolution_id is not None:
        mech = ruleset.resolutions[action.resolution_id]
        mod_expr = action.modifier_override_formula or mech.modifier_formula
        mod_val = _as_scalar_value(evaluate_formula(mod_expr, eval_ctx), "modifier_formula")
        mod_num = (
            mod_val if isinstance(mod_val, (int, float)) and not isinstance(mod_val, bool) else 0
        )

        target_expr = action.target_override_formula or mech.target_formula
        target_num: int | float | None = None
        if target_expr is not None:
            t_raw = evaluate_formula(target_expr, eval_ctx)
            if isinstance(t_raw, (int, float)) and not isinstance(t_raw, bool):
                target_num = t_raw

        seed_default = (
            next(iter(cur_state.rng_streams.values())).seed if cur_state.rng_streams else "scene"
        )
        rng_reg = SceneRngRegistry(seed_default, cur_state.rng_streams)
        dice_stream = rng_reg.stream("dice")
        pos_before = dice_stream.position

        roll_result, updated_decks = resolve_randomizer(
            mech.randomizer,
            dice_stream,
            eval_ctx,
            deck_specs=ruleset.decks,
            deck_states=cur_state.decks,
            modifier_value=mod_num,
            target_value=target_num,
            tiers=mech.tiers,
            wager_bonus=wager_bonus,
        )

        if dice_stream.position != pos_before:
            rng_evt = VmEvent(
                event_id=_next_event_id(cur_state, 0),
                event_type="RNG_ADVANCED",
                actor_id=actor_id,
                payload={"stream_state": dice_stream.snapshot().model_dump(mode="json")},
            )
            emitted.append(rng_evt)
            cur_state = apply_event(ruleset, cur_state, rng_evt)

        for deck_id in sorted(updated_decks):
            if cur_state.decks.get(deck_id) != updated_decks[deck_id]:
                deck_evt = VmEvent(
                    event_id=_next_event_id(cur_state, 0),
                    event_type="DECK_UPDATED",
                    actor_id=actor_id,
                    payload={
                        "deck_id": deck_id,
                        "deck_state": updated_decks[deck_id].model_dump(mode="json"),
                    },
                )
                emitted.append(deck_evt)
                cur_state = apply_event(ruleset, cur_state, deck_evt)

        if roll_result.tier_id is not None:
            for tier in mech.tiers:
                if tier.tier_id == roll_result.tier_id:
                    matched_tier = tier
                    break

    # Apply outcome tier effects and action default_effects
    fresh_actor_view = compute_entity_view(ruleset, cur_state.entities[actor_id])
    fresh_target_view = (
        compute_entity_view(ruleset, cur_state.entities[target_id])
        if target_id is not None
        else None
    )
    effect_ctx: dict[str, object] = {
        "@self": fresh_actor_view.to_eval_context(),
        "@target": fresh_target_view.to_eval_context() if fresh_target_view else None,
        "@roll": (
            {
                "total": roll_result.total,
                "hits": roll_result.hits if roll_result.hits is not None else 0,
                "heads": roll_result.heads_count if roll_result.heads_count is not None else 0,
                "tails": roll_result.tails_count if roll_result.tails_count is not None else 0,
                "symbols": roll_result.symbols,
                "is_glitch": roll_result.is_glitch,
                "tier_id": roll_result.tier_id,
            }
            if roll_result is not None
            else {}
        ),
    }

    if matched_tier is not None:
        for eff in matched_tier.effects:
            cur_state = _resolve_effect_events(
                ruleset,
                cur_state,
                eff,
                actor_id=actor_id,
                target_id=target_id,
                eval_ctx=effect_ctx,
                pending_events=emitted,
            )

    for eff in action.default_effects:
        cur_state = _resolve_effect_events(
            ruleset,
            cur_state,
            eff,
            actor_id=actor_id,
            target_id=target_id,
            eval_ctx=effect_ctx,
            pending_events=emitted,
        )

    exec_evt = VmEvent(
        event_id=_next_event_id(cur_state, 0),
        event_type="ACTION_EXECUTED",
        actor_id=actor_id,
        payload={
            "action_id": action_id,
            "target_id": target_id,
            "tier_id": roll_result.tier_id if roll_result else None,
            "total": roll_result.total if roll_result else None,
        },
    )
    emitted.append(exec_evt)
    cur_state = apply_event(ruleset, cur_state, exec_evt)

    # Fire ECA lifecycle hooks
    cur_state = _fire_event_hooks(
        ruleset,
        cur_state,
        event_name="on_action_resolved",
        actor_id=actor_id,
        target_id=target_id,
        event_data={
            "action_id": action_id,
            "tier_id": roll_result.tier_id if roll_result else None,
            "total": roll_result.total if roll_result else 0,
        },
        emitted=emitted,
    )

    return ActionResolutionResult(
        status="executed",
        state=cur_state,
        events=tuple(emitted),
        roll_result=roll_result,
    )


def resolve_pending_reaction(
    ruleset: RulesetSchema,
    state: SceneState,
    *,
    responses: Sequence[tuple[str, str | None]] = (),
    timed_out: bool = False,
) -> ActionResolutionResult:
    """Apply reaction responses (or timeout) and resume the paused primary action."""
    window = state.pending_reaction
    if window is None:
        raise ValueError("No pending reaction window in SceneState.")

    for t_id, reaction_id in responses:
        window = submit_reaction_response(window, t_id, reaction_id)
    if timed_out and window.status == "PENDING_REACTION":
        window = resolve_reaction_timeout(window)
    elif window.status == "PENDING_REACTION":
        # Wait until all targets respond or timeout
        upd_evt = VmEvent(
            event_id=_next_event_id(state, 0),
            event_type="REACTION_OPENED",
            actor_id=window.actor_id,
            payload={"window": window.model_dump(mode="json")},
        )
        next_state = apply_event(ruleset, state, upd_evt)
        return ActionResolutionResult(
            status="pending_reaction",
            state=next_state,
            events=(upd_evt,),
            pending_window=window,
        )

    emitted: list[VmEvent] = []
    cur_state = state

    # Execute chosen reactions deterministically before resolving pending action
    for prompt in window.prompts:
        if prompt.chosen_reaction_id is not None:
            react_res = execute_action(
                ruleset,
                cur_state,
                actor_id=prompt.target_id,
                action_id=prompt.chosen_reaction_id,
                target_id=window.actor_id,
                bypass_reactions=True,
            )
            cur_state = react_res.state
            emitted.extend(react_res.events)

    resolved_evt = VmEvent(
        event_id=_next_event_id(cur_state, 0),
        event_type="REACTION_RESOLVED",
        actor_id=window.actor_id,
        payload={"window_id": window.window_id, "status": window.status},
    )
    emitted.append(resolved_evt)
    cur_state = apply_event(ruleset, cur_state, resolved_evt)

    resumed = execute_action(
        ruleset,
        cur_state,
        actor_id=window.actor_id,
        action_id=window.pending_action_id,
        target_id=window.target_id,
        manual_roll_mode=window.manual_roll_mode,
        wager_bonus=window.wager_bonus,
        bypass_reactions=True,
    )
    return ActionResolutionResult(
        status=resumed.status,
        state=resumed.state,
        events=(*emitted, *resumed.events),
        roll_result=resumed.roll_result,
        pending_window=resumed.pending_window,
    )


def apply_sheet_override(
    ruleset: RulesetSchema,
    state: SceneState,
    *,
    entity_id: str,
    property_overrides: dict[str, ScalarValue] | None = None,
    pool_overrides: dict[str, int] | None = None,
    add_conditions: Mapping[str, int | None] | Sequence[str] | None = None,
    remove_conditions: Sequence[str] | None = None,
    add_tags: Sequence[str] | None = None,
    remove_tags: Sequence[str] | None = None,
    actor_seat_id: str,
    reason: str = "",
) -> tuple[SceneState, VmEvent]:
    """Commit an audited SHEET_OVERRIDE event for manual roll / direct-edit play modes."""
    if entity_id not in state.entities:
        raise KeyError(f"Unknown entity '{entity_id}'")
    normalized_add_conds: dict[str, int | None] = {}
    if isinstance(add_conditions, Mapping):
        for cid, dur in add_conditions.items():
            normalized_add_conds[cid] = dur
    elif add_conditions is not None:
        for cid in add_conditions:
            cond_def = ruleset.conditions.get(cid)
            normalized_add_conds[cid] = (
                cond_def.default_duration_turns if cond_def is not None else None
            )
    evt = VmEvent(
        event_id=_next_event_id(state, 0),
        event_type="SHEET_OVERRIDE",
        actor_id=actor_seat_id,
        payload={
            "entity_id": entity_id,
            "property_overrides": dict(property_overrides or {}),
            "pool_overrides": dict(pool_overrides or {}),
            "add_conditions": normalized_add_conds,
            "remove_conditions": list(remove_conditions or ()),
            "add_tags": list(add_tags or ()),
            "remove_tags": list(remove_tags or ()),
            "reason": reason,
        },
    )
    return apply_event(ruleset, state, evt), evt
