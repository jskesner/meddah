"""Pure event-sourced Universal Ruleset Virtual Machine."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from app.ruleset_vm.ast_evaluator import FormulaError, ScalarValue, evaluate_formula
from app.ruleset_vm.blocks import EffectSpec, OutcomeTier, RulesetSchema
from app.ruleset_vm.flow_controller import FlowState, create_initial_flow
from app.ruleset_vm.randomizers import DeckRuntimeState, RollResult, resolve_randomizer
from app.ruleset_vm.reaction_window import (
    ReactionWindowState,
    open_reaction_window,
    resolve_reaction_timeout,
    submit_reaction_response,
)
from app.ruleset_vm.rng import RngStreamState, SceneRngRegistry


class ActiveCondition(BaseModel):
    """Runtime status condition attached to an entity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    condition_id: str = Field(min_length=1)
    remaining_turns: int | None = None


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


class ComputedEntityView(BaseModel):
    """Derived runtime view of an entity after topological formulas, conditions & auras."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    entity_id: str
    name: str
    properties: dict[str, ScalarValue]
    pools: dict[str, int]
    pool_maxes: dict[str, int | None]
    conditions: tuple[str, ...]
    tags: tuple[str, ...]
    blocked_tags: tuple[str, ...]

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
    """Compute topological derived properties, condition modifiers, and pool bounds."""
    props: dict[str, ScalarValue] = {
        pid: prop.default_value for pid, prop in ruleset.properties.items()
    }
    for k, v in entity.base_properties.items():
        props[k] = v

    cond_ids = tuple(sorted(entity.conditions))
    blocked_tags: set[str] = set()
    for cid in cond_ids:
        c_def = ruleset.conditions.get(cid)
        if c_def is not None:
            blocked_tags.update(c_def.blocks_tags)

    def _build_ctx(cur_props: dict[str, ScalarValue]) -> dict[str, object]:
        ctx: dict[str, object] = {
            "entity_id": entity.entity_id,
            "name": entity.name,
            "pools": dict(entity.pools),
            "conditions": list(cond_ids),
            "tags": list(entity.tags),
        }
        ctx.update(cur_props)
        for pool_k, pool_v in entity.pools.items():
            if pool_k not in ctx:
                ctx[pool_k] = pool_v
        return ctx

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

    # Pass 2: apply active condition property_modifiers and passive aura_modifiers
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

    return ComputedEntityView(
        entity_id=entity.entity_id,
        name=entity.name,
        properties=props,
        pools=dict(entity.pools),
        pool_maxes=pool_maxes,
        conditions=cond_ids,
        tags=entity.tags,
        blocked_tags=tuple(sorted(blocked_tags)),
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
        updated_pools = dict(entity.pools)
        updated_pools[pool_id] = new_val
        updated_entities = dict(state.entities)
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
        updated_entities = dict(state.entities)
        updated_entities[entity_id] = entity.model_copy(
            update={"base_properties": updated_props, "pools": updated_pools}
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


def _resolve_effect_events(
    ruleset: RulesetSchema,
    state: SceneState,
    effect: EffectSpec,
    *,
    actor_id: str,
    target_id: str | None,
    eval_ctx: dict[str, object],
    pending_events: list[VmEvent],
) -> SceneState:
    """Compile a declarative EffectSpec into deterministic VmEvents and apply them."""
    scope_entity_id: str | None = None
    if effect.target_scope == "self":
        scope_entity_id = actor_id
    elif effect.target_scope == "target":
        scope_entity_id = target_id or actor_id

    if effect.kind == "modify_pool":
        if scope_entity_id is None or scope_entity_id not in state.entities:
            return state
        delta = _as_int_value(evaluate_formula(effect.formula, eval_ctx), "modify_pool delta")
        ent = state.entities[scope_entity_id]
        pool_def = ruleset.resource_pools.get(effect.target_key)
        min_val = pool_def.min_value if pool_def is not None else 0
        view = compute_entity_view(ruleset, ent)
        max_val = view.pool_maxes.get(effect.target_key)
        new_val = ent.pools.get(effect.target_key, 0) + delta
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
                "pool_id": effect.target_key,
                "delta": delta,
                "new_value": new_val,
            },
        )
        pending_events.append(evt)
        return apply_event(ruleset, state, evt)

    if effect.kind == "set_property":
        if scope_entity_id is None or scope_entity_id not in state.entities:
            return state
        new_val = _as_scalar_value(evaluate_formula(effect.formula, eval_ctx), "set_property value")
        evt = VmEvent(
            event_id=_next_event_id(state, 0),
            event_type="PROPERTY_SET",
            actor_id=actor_id,
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
            actor_id=actor_id,
            payload={
                "entity_id": scope_entity_id,
                "op": op,
                "condition_id": effect.target_key,
                "duration_turns": duration,
            },
        )
        pending_events.append(evt)
        return apply_event(ruleset, state, evt)

    if effect.kind == "advance_clock":
        delta = _as_int_value(evaluate_formula(effect.formula, eval_ctx), "clock delta")
        new_val = max(0, state.clocks.get(effect.target_key, 0) + delta)
        evt = VmEvent(
            event_id=_next_event_id(state, 0),
            event_type="CLOCK_ADVANCED",
            actor_id=actor_id,
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
        actor_id=actor_id,
        payload={"message": effect.formula},
    )
    pending_events.append(evt)
    return apply_event(ruleset, state, evt)


def _fire_event_hooks(
    ruleset: RulesetSchema,
    state: SceneState,
    *,
    event_name: str,
    actor_id: str,
    target_id: str | None,
    event_data: dict[str, object],
    emitted: list[VmEvent],
) -> SceneState:
    cur_state = state
    for hook_id in sorted(ruleset.event_hooks):
        hook = ruleset.event_hooks[hook_id]
        if hook.event_name != event_name:
            continue
        actor_view = compute_entity_view(ruleset, cur_state.entities[actor_id])
        target_view = (
            compute_entity_view(ruleset, cur_state.entities[target_id])
            if target_id and target_id in cur_state.entities
            else None
        )
        ctx: dict[str, object] = {
            "@self": actor_view.to_eval_context(),
            "@target": target_view.to_eval_context() if target_view else None,
            "@event": event_data,
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
                )
    return cur_state


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
    actor_seat_id: str,
    reason: str = "",
) -> tuple[SceneState, VmEvent]:
    """Commit an audited SHEET_OVERRIDE event for manual roll / direct-edit play modes."""
    if entity_id not in state.entities:
        raise KeyError(f"Unknown entity '{entity_id}'")
    evt = VmEvent(
        event_id=_next_event_id(state, 0),
        event_type="SHEET_OVERRIDE",
        actor_id=actor_seat_id,
        payload={
            "entity_id": entity_id,
            "property_overrides": dict(property_overrides or {}),
            "pool_overrides": dict(pool_overrides or {}),
            "reason": reason,
        },
    )
    return apply_event(ruleset, state, evt), evt
