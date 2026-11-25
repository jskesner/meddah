"""Universal character transformations, alternate forms & stat-block toggling (ADR-0133)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.ruleset_vm.ast_evaluator import evaluate_formula
from app.ruleset_vm.blocks import FormBlock, GearHandlingMode, RulesetSchema
from app.ruleset_vm.vm import (
    ActiveFormState,
    EntityState,
    SceneState,
    VmEvent,
    apply_event,
    build_active_form_state,
    compute_entity_view,
    trigger_event_hooks,
)


class FormTransitionResult(BaseModel):
    """Audit-complete result of shifting into, reverting, or ticking an alternate form."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    state: SceneState
    events: tuple[VmEvent, ...]
    active_form: ActiveFormState | None = None
    previous_form_id: str | None = None
    gear_handling: GearHandlingMode | None = None
    costs_deducted: dict[str, int] = Field(default_factory=dict)


def _next_event_id(state: SceneState) -> str:
    return f"evt_{state.scene_id}_{state.event_seq + 1:06d}"


def _eval_int_formula(expr: str, eval_ctx: dict[str, object], label: str) -> int:
    raw = evaluate_formula(expr, eval_ctx)
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise ValueError(f"Expected numeric formula result for {label}, got {raw!r}.")
    return int(raw)


def list_available_forms(
    ruleset: RulesetSchema,
    entity: EntityState,
    *,
    include_all_ruleset_forms: bool = False,
) -> tuple[FormBlock, ...]:
    """Return all eligible ruleset forms for entity (or empty tuple when dormant)."""
    if not ruleset.forms:
        return ()

    view = compute_entity_view(ruleset, entity)
    eval_ctx: dict[str, object] = {"@self": view.to_eval_context()}
    eligible: list[FormBlock] = []

    for form_id in sorted(ruleset.forms):
        if not include_all_ruleset_forms and form_id not in entity.available_forms:
            continue
        form = ruleset.forms[form_id]
        if bool(evaluate_formula(form.requires, eval_ctx)):
            eligible.append(form)
    return tuple(eligible)


def can_shift_into_form(
    ruleset: RulesetSchema,
    entity: EntityState,
    form_id: str,
    *,
    require_unlocked: bool = False,
    forced: bool = False,
) -> tuple[bool, str | None]:
    """Validate whether entity satisfies prerequisites, unlock list, and resource costs."""
    form = ruleset.forms.get(form_id)
    if form is None:
        return False, f"Unknown form '{form_id}'."
    if forced:
        return True, None
    if require_unlocked and form_id not in entity.available_forms:
        return False, f"Form '{form_id}' is not unlocked on '{entity.entity_id}'."

    view = compute_entity_view(ruleset, entity)
    eval_ctx: dict[str, object] = {"@self": view.to_eval_context()}
    if not bool(evaluate_formula(form.requires, eval_ctx)):
        return False, f"Prerequisites failed for form '{form_id}'."

    for pool_id, cost_expr in sorted(form.pool_costs.items()):
        cost = _eval_int_formula(cost_expr, eval_ctx, f"form_cost:{pool_id}")
        cur_val = entity.pools.get(pool_id, 0)
        if cur_val < cost:
            return False, f"Insufficient pool '{pool_id}' ({cur_val} < {cost}) for '{form_id}'."

    return True, None


def shift_into_form(
    ruleset: RulesetSchema,
    state: SceneState,
    entity_id: str,
    form_id: str,
    *,
    require_unlocked: bool = False,
    duration_override: int | None = None,
    actor_seat_id: str | None = None,
    forced: bool = False,
    source_entity_id: str | None = None,
) -> FormTransitionResult:
    """Shift entity into a ruleset FormBlock, deducting costs & emitting FORM_CHANGED."""
    if entity_id not in state.entities:
        raise KeyError(f"Unknown entity '{entity_id}'")
    form = ruleset.forms.get(form_id)
    if form is None:
        raise KeyError(f"Unknown ruleset form '{form_id}'")

    ent = state.entities[entity_id]
    costs_deducted: dict[str, int] = {}
    if not forced:
        if require_unlocked and form_id not in ent.available_forms:
            raise PermissionError(f"Form '{form_id}' is not unlocked on '{entity_id}'.")

        view = compute_entity_view(ruleset, ent)
        eval_ctx: dict[str, object] = {"@self": view.to_eval_context()}
        if not bool(evaluate_formula(form.requires, eval_ctx)):
            raise PermissionError(f"Prerequisites failed for form '{form_id}'.")

        for pool_id, cost_expr in sorted(form.pool_costs.items()):
            cost = _eval_int_formula(cost_expr, eval_ctx, f"form_cost:{pool_id}")
            available = ent.pools.get(pool_id, 0)
            if available < cost:
                raise ValueError(
                    f"Insufficient pool '{pool_id}' ({available} < {cost}) for form '{form_id}'."
                )
            costs_deducted[pool_id] = cost

    cur_state = state
    emitted: list[VmEvent] = []
    actor = actor_seat_id or entity_id

    for pool_id, cost in sorted(costs_deducted.items()):
        cur_ent = cur_state.entities[entity_id]
        new_pool_val = cur_ent.pools.get(pool_id, 0) - cost
        pool_evt = VmEvent(
            event_id=_next_event_id(cur_state),
            event_type="POOL_MODIFIED",
            actor_id=actor,
            payload={
                "entity_id": entity_id,
                "pool_id": pool_id,
                "delta": -cost,
                "new_value": new_pool_val,
            },
        )
        emitted.append(pool_evt)
        cur_state = apply_event(ruleset, cur_state, pool_evt)

    fresh_ent = cur_state.entities[entity_id]
    effective_source = source_entity_id if source_entity_id is not None else actor_seat_id
    previous_form_id = fresh_ent.active_form.form_id if fresh_ent.active_form else None
    next_form = build_active_form_state(
        ruleset,
        fresh_ent,
        form,
        duration_override=duration_override,
        involuntary=forced,
        source_entity_id=effective_source,
    )
    shift_evt = VmEvent(
        event_id=_next_event_id(cur_state),
        event_type="FORM_CHANGED",
        actor_id=actor,
        payload={
            "entity_id": entity_id,
            "op": "shift",
            "form_id": form_id,
            "previous_form_id": previous_form_id,
            "gear_handling": form.gear_handling,
            "involuntary": forced,
            "source_entity_id": effective_source,
            "active_form": next_form.model_dump(mode="json"),
        },
    )
    emitted.append(shift_evt)
    cur_state = apply_event(ruleset, cur_state, shift_evt)

    cur_state, hook_events = trigger_event_hooks(
        ruleset,
        cur_state,
        event_name="on_form_entered",
        actor_id=entity_id,
        event_data={
            "entity_id": entity_id,
            "form_id": form_id,
            "previous_form_id": previous_form_id,
            "involuntary": forced,
            "source_entity_id": effective_source,
        },
    )
    emitted.extend(hook_events)
    final_form = cur_state.entities[entity_id].active_form

    return FormTransitionResult(
        state=cur_state,
        events=tuple(emitted),
        active_form=final_form,
        previous_form_id=previous_form_id,
        gear_handling=form.gear_handling,
        costs_deducted=costs_deducted,
    )


def revert_form(
    ruleset: RulesetSchema,
    state: SceneState,
    entity_id: str,
    *,
    reason: str = "manual_revert",
    actor_seat_id: str | None = None,
    forced: bool = False,
) -> FormTransitionResult:
    """Revert an entity from any active alternate form back to its base state."""
    if entity_id not in state.entities:
        raise KeyError(f"Unknown entity '{entity_id}'")
    ent = state.entities[entity_id]
    if ent.active_form is None:
        return FormTransitionResult(
            state=state,
            events=(),
            active_form=None,
            previous_form_id=None,
        )
    if ent.active_form.involuntary and not forced:
        raise PermissionError(
            f"Active form '{ent.active_form.form_id}' on '{entity_id}' "
            "is involuntary and requires forced=True to revert."
        )

    prev_form = ent.active_form
    prev_id = prev_form.form_id
    gear_handling = prev_form.gear_handling
    evt = VmEvent(
        event_id=_next_event_id(state),
        event_type="FORM_CHANGED",
        actor_id=actor_seat_id or entity_id,
        payload={
            "entity_id": entity_id,
            "op": "revert",
            "form_id": prev_id,
            "reason": reason,
            "forced": forced,
        },
    )
    cur_state = apply_event(ruleset, state, evt)
    cur_state, hook_events = trigger_event_hooks(
        ruleset,
        cur_state,
        event_name="on_form_reverted",
        actor_id=entity_id,
        event_data={
            "entity_id": entity_id,
            "form_id": prev_id,
            "reason": reason,
            "forced": forced,
            "was_involuntary": prev_form.involuntary,
            "source_entity_id": prev_form.source_entity_id,
        },
    )
    final_form = cur_state.entities[entity_id].active_form
    return FormTransitionResult(
        state=cur_state,
        events=(evt, *hook_events),
        active_form=final_form,
        previous_form_id=prev_id,
        gear_handling=gear_handling,
    )


def tick_active_form(
    ruleset: RulesetSchema,
    state: SceneState,
    entity_id: str,
    *,
    turns: int = 1,
    actor_seat_id: str | None = None,
) -> FormTransitionResult:
    """Decrement remaining duration on a timed form and revert when duration expires."""
    if turns < 1:
        raise ValueError("turns must be >= 1.")
    if entity_id not in state.entities:
        raise KeyError(f"Unknown entity '{entity_id}'")
    ent = state.entities[entity_id]
    prev_form = ent.active_form
    if prev_form is None or prev_form.remaining_turns is None:
        return FormTransitionResult(
            state=state,
            events=(),
            active_form=prev_form,
            previous_form_id=prev_form.form_id if prev_form else None,
            gear_handling=prev_form.gear_handling if prev_form else None,
        )

    prev_id = prev_form.form_id
    gear_handling = prev_form.gear_handling
    next_remaining = max(0, prev_form.remaining_turns - turns)
    evt = VmEvent(
        event_id=_next_event_id(state),
        event_type="FORM_CHANGED",
        actor_id=actor_seat_id or entity_id,
        payload={
            "entity_id": entity_id,
            "op": "tick",
            "form_id": prev_id,
            "remaining_turns": next_remaining,
        },
    )
    next_state = apply_event(ruleset, state, evt)
    hook_events: tuple[VmEvent, ...] = ()
    if next_remaining == 0:
        next_state, hook_events = trigger_event_hooks(
            ruleset,
            next_state,
            event_name="on_form_reverted",
            actor_id=entity_id,
            event_data={
                "entity_id": entity_id,
                "form_id": prev_id,
                "reason": "duration_expired",
                "forced": True,
                "was_involuntary": prev_form.involuntary,
                "source_entity_id": prev_form.source_entity_id,
            },
        )
    updated_form = next_state.entities[entity_id].active_form
    return FormTransitionResult(
        state=next_state,
        events=(evt, *hook_events),
        active_form=updated_form,
        previous_form_id=prev_id,
        gear_handling=gear_handling,
    )
