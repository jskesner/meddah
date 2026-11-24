"""Pluggable Turn & Time Flow Controller (freeform, round_initiative, popcorn_spotlight)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.ruleset_vm.blocks import FlowConfig, RandomizerSpec, RulesetSchema
from app.ruleset_vm.randomizers import resolve_randomizer
from app.ruleset_vm.rng import DeterministicRngStream

FlowMode = Literal["freeform", "round_initiative", "popcorn_spotlight"]


class FlowState(BaseModel):
    """Serializable scene turn-order and spotlight tracking state."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: FlowMode = "freeform"
    round_number: int = Field(default=0, ge=0)
    turn_order: tuple[str, ...] = ()
    initiative_scores: dict[str, int | float] = Field(default_factory=dict)
    active_entity_id: str | None = None
    acted_this_round: tuple[str, ...] = ()
    delayed_entities: tuple[str, ...] = ()


def create_initial_flow(config: FlowConfig) -> FlowState:
    """Create initial FlowState matching a ruleset's FlowConfig default mode."""
    return FlowState(
        mode=config.default_mode,
        round_number=1 if config.default_mode != "freeform" else 0,
    )


def start_round_initiative(
    ruleset: RulesetSchema,
    entity_contexts: Mapping[str, Mapping[str, object]],
    rng: DeterministicRngStream,
) -> FlowState:
    """Roll ruleset initiative_formula deterministically across entities and sort turn queue."""
    formula = ruleset.flow_config.initiative_formula.strip() or "0"
    init_spec = RandomizerSpec(kind="dice_formula", formula=formula)

    scored: list[tuple[int | float, str]] = []
    scores_map: dict[str, int | float] = {}
    for entity_id in sorted(entity_contexts):
        eval_ctx = {"@self": entity_contexts[entity_id]}
        roll_res, _ = resolve_randomizer(init_spec, rng, eval_ctx)
        scores_map[entity_id] = roll_res.total
        scored.append((roll_res.total, entity_id))

    # Descending initiative score, tie-broken deterministically by entity_id ascending
    ordered = [eid for _, eid in sorted(scored, key=lambda pair: (-pair[0], pair[1]))]
    active = ordered[0] if ordered else None
    return FlowState(
        mode="round_initiative",
        round_number=1,
        turn_order=tuple(ordered),
        initiative_scores=scores_map,
        active_entity_id=active,
        acted_this_round=(),
        delayed_entities=(),
    )


def advance_turn(state: FlowState) -> FlowState:
    """Advance to the next actor in round_initiative, wrapping into next round."""
    if state.mode != "round_initiative" or not state.turn_order:
        return state

    acted = list(state.acted_this_round)
    if state.active_entity_id and state.active_entity_id not in acted:
        acted.append(state.active_entity_id)

    try:
        cur_idx = state.turn_order.index(state.active_entity_id) if state.active_entity_id else -1
    except ValueError:
        cur_idx = -1

    next_idx = cur_idx + 1
    if next_idx >= len(state.turn_order):
        return state.model_copy(
            update={
                "round_number": state.round_number + 1,
                "active_entity_id": state.turn_order[0],
                "acted_this_round": (),
                "delayed_entities": (),
            }
        )

    return state.model_copy(
        update={
            "active_entity_id": state.turn_order[next_idx],
            "acted_this_round": tuple(acted),
        }
    )


def delay_turn(state: FlowState, entity_id: str) -> FlowState:
    """Move an entity to the end of the current turn order and advance if active."""
    if state.mode != "round_initiative" or entity_id not in state.turn_order:
        return state

    remaining = [eid for eid in state.turn_order if eid != entity_id]
    new_order = (*remaining, entity_id)
    delayed = tuple(dict.fromkeys([*state.delayed_entities, entity_id]))

    if state.active_entity_id == entity_id and remaining:
        old_idx = state.turn_order.index(entity_id)
        candidate_idx = min(old_idx, len(new_order) - 1)
        next_active: str | None = new_order[candidate_idx]
    else:
        next_active = state.active_entity_id

    return state.model_copy(
        update={
            "turn_order": new_order,
            "active_entity_id": next_active,
            "delayed_entities": delayed,
        }
    )


def handoff_spotlight(
    state: FlowState,
    next_entity_id: str,
    participant_ids: Sequence[str],
) -> FlowState:
    """Pass spotlight in popcorn_spotlight mode, tracking acted tokens per round."""
    if next_entity_id not in participant_ids:
        raise ValueError(f"Unknown spotlight participant '{next_entity_id}'")

    acted = list(state.acted_this_round)
    if state.active_entity_id and state.active_entity_id not in acted:
        acted.append(state.active_entity_id)

    unique_participants = set(participant_ids)
    if unique_participants and unique_participants.issubset(set(acted)):
        return FlowState(
            mode="popcorn_spotlight",
            round_number=max(1, state.round_number) + 1,
            turn_order=tuple(participant_ids),
            active_entity_id=next_entity_id,
            acted_this_round=(),
        )

    return state.model_copy(
        update={
            "mode": "popcorn_spotlight",
            "round_number": max(1, state.round_number),
            "turn_order": tuple(participant_ids),
            "active_entity_id": next_entity_id,
            "acted_this_round": tuple(acted),
        }
    )


def switch_flow_mode(
    state: FlowState,
    mode: FlowMode,
    *,
    ruleset: RulesetSchema | None = None,
    entity_contexts: Mapping[str, Mapping[str, object]] | None = None,
    rng: DeterministicRngStream | None = None,
    spotlight_entity_id: str | None = None,
) -> FlowState:
    """Transition cleanly between freeform, round_initiative, and popcorn_spotlight."""
    if mode == "freeform":
        return FlowState(mode="freeform", round_number=0)
    if mode == "round_initiative":
        if ruleset is not None and entity_contexts is not None and rng is not None:
            return start_round_initiative(ruleset, entity_contexts, rng)
        return FlowState(
            mode="round_initiative",
            round_number=max(1, state.round_number),
            turn_order=tuple(sorted(entity_contexts)) if entity_contexts else (),
            active_entity_id=min(entity_contexts) if entity_contexts else None,
        )
    participants = tuple(sorted(entity_contexts)) if entity_contexts else ()
    active = spotlight_entity_id or (participants[0] if participants else None)
    return FlowState(
        mode="popcorn_spotlight",
        round_number=max(1, state.round_number),
        turn_order=participants,
        active_entity_id=active,
    )
