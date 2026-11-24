"""Explicit Reaction & Contested Roll Window state machine (§1.1.2)."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.ruleset_vm.ast_evaluator import FormulaError, evaluate_formula
from app.ruleset_vm.blocks import RulesetSchema


class ReactionPrompt(BaseModel):
    """Eligible reactions offered to a single targeted entity during PENDING_REACTION."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    target_id: str = Field(min_length=1)
    eligible_reaction_ids: tuple[str, ...]
    responded: bool = False
    chosen_reaction_id: str | None = None


class ReactionWindowState(BaseModel):
    """Paused action resolution awaiting explicit target reaction or timeout."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    window_id: str = Field(min_length=1)
    pending_action_id: str = Field(min_length=1)
    actor_id: str = Field(min_length=1)
    target_id: str | None = None
    status: Literal["PENDING_REACTION", "RESOLVED", "TIMED_OUT"] = "PENDING_REACTION"
    timeout_seconds: int = Field(default=30, ge=1)
    prompts: tuple[ReactionPrompt, ...] = ()
    manual_roll_mode: bool = False
    wager_bonus: int | float = 0


def open_reaction_window(
    *,
    window_id: str,
    pending_action_id: str,
    actor_id: str,
    target_ids: Sequence[str],
    ruleset: RulesetSchema,
    entity_views: Mapping[str, Mapping[str, object]],
    entity_pools: Mapping[str, Mapping[str, int]],
    trigger_name: str = "on_targeted",
    can_afford_fn: Callable[[str, Mapping[str, str], Mapping[str, object]], bool] | None = None,
    timeout_seconds: int = 30,
    manual_roll_mode: bool = False,
    wager_bonus: int | float = 0,
) -> ReactionWindowState | None:
    """Query targets for valid reactions passing AST preconditions & costs."""
    actor_view = entity_views.get(actor_id, {})
    candidate_reactions = [
        action
        for action in ruleset.actions.values()
        if action.category == "reaction" and action.trigger == trigger_name
    ]
    if not candidate_reactions:
        return None

    prompts: list[ReactionPrompt] = []
    for target_id in target_ids:
        target_view = entity_views.get(target_id)
        if target_view is None:
            continue
        eval_ctx: dict[str, object] = {"@self": target_view, "@target": actor_view}
        eligible: list[str] = []
        target_pool_map = entity_pools.get(target_id, {})

        for reaction in sorted(candidate_reactions, key=lambda a: a.action_id):
            try:
                allowed = bool(evaluate_formula(reaction.requires, eval_ctx))
            except FormulaError:
                allowed = False
            if not allowed:
                continue

            if can_afford_fn is not None:
                if not can_afford_fn(target_id, reaction.pool_costs, eval_ctx):
                    continue
            else:
                affordable = True
                for pool_id, cost_expr in reaction.pool_costs.items():
                    cost_val = evaluate_formula(cost_expr, eval_ctx)
                    if not isinstance(cost_val, (int, float)) or target_pool_map.get(
                        pool_id, 0
                    ) < int(cost_val):
                        affordable = False
                        break
                if not affordable:
                    continue

            eligible.append(reaction.action_id)

        if eligible:
            prompts.append(
                ReactionPrompt(target_id=target_id, eligible_reaction_ids=tuple(eligible))
            )

    if not prompts:
        return None

    return ReactionWindowState(
        window_id=window_id,
        pending_action_id=pending_action_id,
        actor_id=actor_id,
        target_id=target_ids[0] if len(target_ids) == 1 else None,
        status="PENDING_REACTION",
        timeout_seconds=timeout_seconds,
        prompts=tuple(prompts),
        manual_roll_mode=manual_roll_mode,
        wager_bonus=wager_bonus,
    )


def submit_reaction_response(
    window: ReactionWindowState,
    target_id: str,
    reaction_action_id: str | None,
) -> ReactionWindowState:
    """Record a target's reaction selection (or explicit decline via None)."""
    if window.status != "PENDING_REACTION":
        raise ValueError(f"Reaction window '{window.window_id}' is already {window.status}.")

    updated_prompts: list[ReactionPrompt] = []
    found = False
    for prompt in window.prompts:
        if prompt.target_id == target_id:
            found = True
            if (
                reaction_action_id is not None
                and reaction_action_id not in prompt.eligible_reaction_ids
            ):
                raise ValueError(
                    f"Reaction '{reaction_action_id}' is not eligible for '{target_id}'."
                )
            updated_prompts.append(
                prompt.model_copy(
                    update={"responded": True, "chosen_reaction_id": reaction_action_id}
                )
            )
        else:
            updated_prompts.append(prompt)

    if not found:
        raise KeyError(f"No reaction prompt exists for target '{target_id}'.")

    all_done = all(p.responded for p in updated_prompts)
    return window.model_copy(
        update={
            "prompts": tuple(updated_prompts),
            "status": "RESOLVED" if all_done else "PENDING_REACTION",
        }
    )


def resolve_reaction_timeout(window: ReactionWindowState) -> ReactionWindowState:
    """Resolve an expired reaction window, marking unresponded targets as declined."""
    if window.status != "PENDING_REACTION":
        return window
    updated_prompts = tuple(
        prompt.model_copy(update={"responded": True}) if not prompt.responded else prompt
        for prompt in window.prompts
    )
    return window.model_copy(
        update={
            "prompts": updated_prompts,
            "status": "TIMED_OUT",
        }
    )
