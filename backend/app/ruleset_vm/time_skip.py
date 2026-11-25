"""Hybrid Synchronized Time Skips & Non-Blocking Timed Activities (ADR-0135)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.ruleset_vm.blocks import RulesetSchema
from app.ruleset_vm.module_registry import MeddahModuleManifest, ModuleProvides, SeatRole
from app.ruleset_vm.vm import (
    ActiveDisguiseState,
    ActiveTimedActivity,
    ConcurrentActivitySelection,
    SceneState,
    TimedActivityCategory,
    TimeSkipConsensusMode,
    TimeSkipProposal,
    TimeSkipVoteChoice,
    VmEvent,
    apply_event,
    trigger_event_hooks,
)

MODULE_MANIFEST = MeddahModuleManifest(
    module_id="synchronized_time_skip",
    spec_section="1.5.7",
    label="Synchronized Time Skips & Non-Blocking Timed Activities",
    requires_primitives=(),
    provides=ModuleProvides(
        commands=("timeskip", "wait", "schedule_activity"),
        ui_panels=("time_skip_proposal_bar", "active_timed_tasks_badge"),
        event_hooks=(
            "on_world_time_advanced",
            "on_timed_activity_started",
            "on_timed_activity_completed",
            "on_timed_activity_interrupted",
            "on_time_skip_proposed",
            "on_time_skip_committed",
            "on_time_skip_interrupted",
        ),
        schema_blocks=(
            "ActiveTimedActivity",
            "TimeSkipProposal",
            "ConcurrentActivitySelection",
        ),
    ),
    scope="campaign",
    ai_dependency="none",
)

TIME_SKIP_MODULE_MANIFEST = MODULE_MANIFEST


class TimeSkipTransitionResult(BaseModel):
    """Audit-complete result of a timed activity, vote, advance, or time-skip transition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    state: SceneState
    events: tuple[VmEvent, ...]
    proposal: TimeSkipProposal | None = None
    activity: ActiveTimedActivity | None = None
    completed_activities: tuple[ActiveTimedActivity, ...] = ()
    elapsed_seconds_advanced: int = 0


def _next_event_id(state: SceneState) -> str:
    return f"evt_{state.scene_id}_{state.event_seq + 1:06d}"


def _has_consensus(
    proposal: TimeSkipProposal,
    votes: Mapping[str, TimeSkipVoteChoice],
) -> bool:
    if proposal.consensus_mode == "gm_only":
        return False
    if "hold_act_first" in votes.values():
        return False
    if proposal.required_voter_seat_ids:
        voters = proposal.required_voter_seat_ids
        if proposal.consensus_mode == "unanimous":
            return all(votes.get(seat) == "approve" for seat in voters)
        approve_count = sum(1 for seat in voters if votes.get(seat) == "approve")
        return approve_count * 2 > len(voters)
    return any(choice == "approve" for choice in votes.values())


def _apply_completed_activity_payload(
    ruleset: RulesetSchema,
    state: SceneState,
    activity: ActiveTimedActivity,
    *,
    actor_seat_id: str,
    emitted: list[VmEvent],
) -> SceneState:
    payload = activity.completion_payload
    kind = payload.get("kind")
    if activity.entity_id not in state.entities:
        return state
    entity = state.entities[activity.entity_id]

    if kind == "apply_disguise_preset":
        preset_id = str(payload.get("preset_id", ""))
        preset = entity.disguise_presets.get(preset_id)
        if preset is None:
            return state
        raw_quality = payload.get("quality_score")
        quality: int | float | None = (
            raw_quality
            if isinstance(raw_quality, (int, float)) and not isinstance(raw_quality, bool)
            else None
        )
        disguise = ActiveDisguiseState(
            alias_id=preset.alias_id,
            presented_name=preset.presented_name,
            presented_tags=preset.presented_tags,
            disguise_source=preset.disguise_source,
            quality_score=quality,
            voice_disguised=preset.voice_disguised,
            portrait_override_ref=preset.portrait_override_ref,
            token_override_ref=preset.token_override_ref,
        )
        raw_outfit_id = payload.get("outfit_preset_id")
        outfit_id = (
            raw_outfit_id
            if isinstance(raw_outfit_id, str) and raw_outfit_id
            else preset.outfit_preset_id
        )
        evt = VmEvent(
            event_id=_next_event_id(state),
            event_type="DISGUISE_CHANGED",
            actor_id=actor_seat_id,
            payload={
                "entity_id": activity.entity_id,
                "op": "apply",
                "active_disguise": disguise.model_dump(mode="json"),
                "outfit_preset_id": outfit_id,
                "preset_id": preset.preset_id,
            },
        )
        emitted.append(evt)
        cur_state = apply_event(ruleset, state, evt)
        cur_state, hook_events = trigger_event_hooks(
            ruleset,
            cur_state,
            event_name="on_disguise_applied",
            actor_id=activity.entity_id,
            event_data={
                "entity_id": activity.entity_id,
                "alias_id": preset.alias_id,
                "presented_name": preset.presented_name,
                "quality_score": quality,
                "disguise_source": preset.disguise_source,
                "preset_id": preset.preset_id,
            },
        )
        emitted.extend(hook_events)
        return cur_state

    if kind == "apply_disguise":
        raw_disguise = payload.get("active_disguise")
        if not isinstance(raw_disguise, Mapping):
            return state
        disguise = ActiveDisguiseState.model_validate(raw_disguise)
        raw_outfit_id = payload.get("outfit_preset_id")
        evt = VmEvent(
            event_id=_next_event_id(state),
            event_type="DISGUISE_CHANGED",
            actor_id=actor_seat_id,
            payload={
                "entity_id": activity.entity_id,
                "op": "apply",
                "active_disguise": disguise.model_dump(mode="json"),
                "outfit_preset_id": (raw_outfit_id if isinstance(raw_outfit_id, str) else None),
            },
        )
        emitted.append(evt)
        cur_state = apply_event(ruleset, state, evt)
        cur_state, hook_events = trigger_event_hooks(
            ruleset,
            cur_state,
            event_name="on_disguise_applied",
            actor_id=activity.entity_id,
            event_data={
                "entity_id": activity.entity_id,
                "alias_id": disguise.alias_id,
                "presented_name": disguise.presented_name,
                "quality_score": disguise.quality_score,
                "disguise_source": disguise.disguise_source,
            },
        )
        emitted.extend(hook_events)
        return cur_state

    return state


def start_timed_activity(
    ruleset: RulesetSchema,
    state: SceneState,
    entity_id: str,
    label: str,
    duration_seconds: int,
    *,
    category: TimedActivityCategory = "custom",
    interruptible: bool = True,
    room_id: str | None = None,
    completion_payload: Mapping[str, object] | None = None,
    actor_seat_id: str | None = None,
) -> TimeSkipTransitionResult:
    """Register a non-blocking timed activity that advances monotonically with world time."""
    if entity_id not in state.entities:
        raise KeyError(f"Unknown entity '{entity_id}'")
    if duration_seconds < 1:
        raise ValueError("duration_seconds must be >= 1.")

    activity_id = f"act_{state.scene_id}_{state.event_seq + 1:06d}_{entity_id}"
    activity = ActiveTimedActivity(
        activity_id=activity_id,
        entity_id=entity_id,
        label=label,
        category=category,
        total_seconds=duration_seconds,
        remaining_seconds=duration_seconds,
        elapsed_seconds=0,
        interruptible=interruptible,
        status="in_progress",
        room_id=room_id,
        completion_payload=dict(completion_payload or {}),
    )
    evt = VmEvent(
        event_id=_next_event_id(state),
        event_type="TIMED_ACTIVITY_UPDATED",
        actor_id=actor_seat_id or entity_id,
        payload={
            "entity_id": entity_id,
            "op": "upsert",
            "activity": activity.model_dump(mode="json"),
        },
    )
    emitted: list[VmEvent] = [evt]
    cur_state = apply_event(ruleset, state, evt)
    cur_state, hook_events = trigger_event_hooks(
        ruleset,
        cur_state,
        event_name="on_timed_activity_started",
        actor_id=entity_id,
        event_data={
            "activity_id": activity_id,
            "entity_id": entity_id,
            "label": label,
            "category": category,
            "duration_seconds": duration_seconds,
            "room_id": room_id,
        },
    )
    emitted.extend(hook_events)
    return TimeSkipTransitionResult(
        state=cur_state,
        events=tuple(emitted),
        activity=cur_state.active_timed_activities.get(entity_id, activity),
    )


def cancel_timed_activity(
    ruleset: RulesetSchema,
    state: SceneState,
    entity_id: str,
    *,
    reason: str = "cancelled",
    actor_seat_id: str | None = None,
) -> TimeSkipTransitionResult:
    """Cancel and remove an entity's active timed activity, firing interruption hooks."""
    existing = state.active_timed_activities.get(entity_id)
    if existing is None:
        return TimeSkipTransitionResult(state=state, events=())

    evt = VmEvent(
        event_id=_next_event_id(state),
        event_type="TIMED_ACTIVITY_UPDATED",
        actor_id=actor_seat_id or entity_id,
        payload={"entity_id": entity_id, "op": "remove", "reason": reason},
    )
    emitted: list[VmEvent] = [evt]
    cur_state = apply_event(ruleset, state, evt)
    if entity_id in cur_state.entities:
        cur_state, hook_events = trigger_event_hooks(
            ruleset,
            cur_state,
            event_name="on_timed_activity_interrupted",
            actor_id=entity_id,
            event_data={
                "activity_id": existing.activity_id,
                "entity_id": entity_id,
                "label": existing.label,
                "elapsed_seconds": existing.elapsed_seconds,
                "remaining_seconds": existing.remaining_seconds,
                "reason": reason,
            },
        )
        emitted.extend(hook_events)
    return TimeSkipTransitionResult(
        state=cur_state,
        events=tuple(emitted),
        activity=existing.model_copy(update={"status": "cancelled"}),
    )


def propose_time_skip(
    ruleset: RulesetSchema,
    state: SceneState,
    proposer_entity_id: str,
    label: str,
    duration_seconds: int,
    *,
    proposer_seat_id: str | None = None,
    required_voter_seat_ids: Sequence[str] = (),
    consensus_mode: TimeSkipConsensusMode = "unanimous",
    auto_commit_if_solo: bool = False,
) -> TimeSkipTransitionResult:
    """Open a non-blocking synchronized TimeSkipProposal for table voting & concurrent prep."""
    if state.pending_time_skip is not None and state.pending_time_skip.status in {"open", "held"}:
        raise ValueError("A time skip proposal is already open or held.")
    if duration_seconds < 1:
        raise ValueError("duration_seconds must be >= 1.")

    seat_id = proposer_seat_id or proposer_entity_id
    voters = tuple(dict.fromkeys(required_voter_seat_ids))
    proposal = TimeSkipProposal(
        proposal_id=f"skip_{state.scene_id}_{state.event_seq + 1:06d}",
        proposer_entity_id=proposer_entity_id,
        proposer_seat_id=seat_id,
        label=label,
        duration_seconds=duration_seconds,
        required_voter_seat_ids=voters,
        votes={seat_id: "approve"},
        consensus_mode=consensus_mode,
        status="open",
    )
    evt = VmEvent(
        event_id=_next_event_id(state),
        event_type="TIME_SKIP_UPDATED",
        actor_id=seat_id,
        payload={"proposal": proposal.model_dump(mode="json")},
    )
    emitted: list[VmEvent] = [evt]
    cur_state = apply_event(ruleset, state, evt)

    hook_actor = proposer_entity_id if proposer_entity_id in cur_state.entities else None
    cur_state, hook_events = trigger_event_hooks(
        ruleset,
        cur_state,
        event_name="on_time_skip_proposed",
        actor_id=hook_actor,
        event_data={
            "proposal_id": proposal.proposal_id,
            "label": label,
            "duration_seconds": duration_seconds,
            "proposer_seat_id": seat_id,
            "consensus_mode": consensus_mode,
        },
    )
    emitted.extend(hook_events)

    should_auto_commit = (
        auto_commit_if_solo and consensus_mode != "gm_only" and (not voters or voters == (seat_id,))
    )
    if should_auto_commit:
        commit_res = commit_time_skip(ruleset, cur_state, actor_seat_id=seat_id)
        emitted.extend(commit_res.events)
        return TimeSkipTransitionResult(
            state=commit_res.state,
            events=tuple(emitted),
            proposal=commit_res.proposal,
            completed_activities=commit_res.completed_activities,
            elapsed_seconds_advanced=commit_res.elapsed_seconds_advanced,
        )

    return TimeSkipTransitionResult(
        state=cur_state,
        events=tuple(emitted),
        proposal=cur_state.pending_time_skip,
    )


def schedule_concurrent_activity(
    ruleset: RulesetSchema,
    state: SceneState,
    entity_id: str,
    activity_label: str,
    *,
    category: TimedActivityCategory = "custom",
    action_id: str | None = None,
    notes: str = "",
    actor_seat_id: str | None = None,
) -> TimeSkipTransitionResult:
    """Attach a player or companion activity to run concurrently during the open time skip."""
    prop = state.pending_time_skip
    if prop is None or prop.status not in {"open", "held"}:
        raise ValueError("No open or held time skip proposal to schedule an activity into.")
    if entity_id not in state.entities:
        raise KeyError(f"Unknown entity '{entity_id}'")
    if action_id is not None and action_id not in ruleset.actions:
        raise KeyError(f"Unknown ruleset action '{action_id}'")

    updated_concurrent = dict(prop.concurrent_activities)
    updated_concurrent[entity_id] = ConcurrentActivitySelection(
        entity_id=entity_id,
        activity_label=activity_label,
        category=category,
        action_id=action_id,
        notes=notes,
    )
    next_prop = prop.model_copy(update={"concurrent_activities": updated_concurrent})
    evt = VmEvent(
        event_id=_next_event_id(state),
        event_type="TIME_SKIP_UPDATED",
        actor_id=actor_seat_id or entity_id,
        payload={"proposal": next_prop.model_dump(mode="json")},
    )
    cur_state = apply_event(ruleset, state, evt)
    return TimeSkipTransitionResult(
        state=cur_state,
        events=(evt,),
        proposal=cur_state.pending_time_skip,
    )


def advance_world_time(
    ruleset: RulesetSchema,
    state: SceneState,
    seconds: int,
    *,
    actor_seat_id: str = "system",
    reason: str = "time_advance",
) -> TimeSkipTransitionResult:
    """Advance authoritative campaign clock and resolve any completed timed activities."""
    if seconds < 0:
        raise ValueError("seconds must be >= 0.")

    to_complete = tuple(
        sorted(
            eid
            for eid, act in state.active_timed_activities.items()
            if act.status == "in_progress" and act.remaining_seconds <= seconds
        )
    )
    adv_evt = VmEvent(
        event_id=_next_event_id(state),
        event_type="WORLD_TIME_ADVANCED",
        actor_id=actor_seat_id,
        payload={"seconds": seconds, "reason": reason},
    )
    emitted: list[VmEvent] = [adv_evt]
    cur_state = apply_event(ruleset, state, adv_evt)

    completed_snapshots: list[ActiveTimedActivity] = []
    for eid in to_complete:
        done_act = cur_state.active_timed_activities.get(eid)
        if done_act is None:
            continue
        completed_snapshots.append(done_act)
        cur_state = _apply_completed_activity_payload(
            ruleset,
            cur_state,
            done_act,
            actor_seat_id=actor_seat_id,
            emitted=emitted,
        )
        rem_evt = VmEvent(
            event_id=_next_event_id(cur_state),
            event_type="TIMED_ACTIVITY_UPDATED",
            actor_id=actor_seat_id,
            payload={"entity_id": eid, "op": "remove", "reason": "completed"},
        )
        emitted.append(rem_evt)
        cur_state = apply_event(ruleset, cur_state, rem_evt)

        hook_actor = eid if eid in cur_state.entities else None
        cur_state, hook_events = trigger_event_hooks(
            ruleset,
            cur_state,
            event_name="on_timed_activity_completed",
            actor_id=hook_actor,
            event_data={
                "activity_id": done_act.activity_id,
                "entity_id": eid,
                "label": done_act.label,
                "category": done_act.category,
                "total_seconds": done_act.total_seconds,
            },
        )
        emitted.extend(hook_events)

    cur_state, world_hooks = trigger_event_hooks(
        ruleset,
        cur_state,
        event_name="on_world_time_advanced",
        actor_id=None,
        event_data={
            "seconds": seconds,
            "elapsed_world_seconds": cur_state.elapsed_world_seconds,
            "reason": reason,
        },
    )
    emitted.extend(world_hooks)
    return TimeSkipTransitionResult(
        state=cur_state,
        events=tuple(emitted),
        completed_activities=tuple(completed_snapshots),
        elapsed_seconds_advanced=seconds,
    )


def commit_time_skip(
    ruleset: RulesetSchema,
    state: SceneState,
    *,
    actor_seat_id: str = "system",
    force: bool = False,
) -> TimeSkipTransitionResult:
    """Advance world clock for the remaining duration of the pending TimeSkipProposal."""
    prop = state.pending_time_skip
    if prop is None or prop.status not in {"open", "held"}:
        raise ValueError("No active time skip proposal to commit.")
    if not force and (prop.status == "held" or "hold_act_first" in prop.votes.values()):
        raise PermissionError(
            "Time skip proposal is held by a player acting first; pass force=True to override."
        )

    rem_seconds = max(0, prop.duration_seconds - prop.elapsed_seconds)
    emitted: list[VmEvent] = []
    adv_res = advance_world_time(
        ruleset,
        state,
        rem_seconds,
        actor_seat_id=actor_seat_id,
        reason=prop.label,
    )
    cur_state = adv_res.state
    emitted.extend(adv_res.events)

    committed_prop = prop.model_copy(
        update={
            "status": "committed",
            "elapsed_seconds": prop.duration_seconds,
        }
    )
    clear_evt = VmEvent(
        event_id=_next_event_id(cur_state),
        event_type="TIME_SKIP_UPDATED",
        actor_id=actor_seat_id,
        payload={"proposal": None, "committed_proposal_id": prop.proposal_id},
    )
    emitted.append(clear_evt)
    cur_state = apply_event(ruleset, cur_state, clear_evt)

    hook_actor = prop.proposer_entity_id if prop.proposer_entity_id in cur_state.entities else None
    cur_state, hook_events = trigger_event_hooks(
        ruleset,
        cur_state,
        event_name="on_time_skip_committed",
        actor_id=hook_actor,
        event_data={
            "proposal_id": prop.proposal_id,
            "label": prop.label,
            "duration_seconds": prop.duration_seconds,
            "advanced_seconds": rem_seconds,
            "concurrent_count": len(prop.concurrent_activities),
        },
    )
    emitted.extend(hook_events)
    return TimeSkipTransitionResult(
        state=cur_state,
        events=tuple(emitted),
        proposal=committed_prop,
        completed_activities=adv_res.completed_activities,
        elapsed_seconds_advanced=rem_seconds,
    )


def vote_on_time_skip(
    ruleset: RulesetSchema,
    state: SceneState,
    seat_id: str,
    choice: TimeSkipVoteChoice,
    *,
    auto_commit_on_consensus: bool = True,
) -> TimeSkipTransitionResult:
    """Record a player vote on an open time skip, keeping split-room exploration non-blocking."""
    prop = state.pending_time_skip
    if prop is None or prop.status not in {"open", "held"}:
        raise ValueError("No active time skip proposal to vote on.")

    if choice == "keep_exploring":
        # Dismiss table-wide sync pause while leaving background timed activities running cleanly
        clear_evt = VmEvent(
            event_id=_next_event_id(state),
            event_type="TIME_SKIP_UPDATED",
            actor_id=seat_id,
            payload={"proposal": None, "dismissed_by": seat_id},
        )
        cur_state = apply_event(ruleset, state, clear_evt)
        return TimeSkipTransitionResult(state=cur_state, events=(clear_evt,), proposal=None)

    votes = dict(prop.votes)
    votes[seat_id] = choice
    if choice == "hold_act_first":
        next_status = "held"
    elif prop.status == "held" and "hold_act_first" not in votes.values():
        next_status = "open"
    else:
        next_status = prop.status

    next_prop = prop.model_copy(update={"votes": votes, "status": next_status})
    evt = VmEvent(
        event_id=_next_event_id(state),
        event_type="TIME_SKIP_UPDATED",
        actor_id=seat_id,
        payload={"proposal": next_prop.model_dump(mode="json")},
    )
    emitted: list[VmEvent] = [evt]
    cur_state = apply_event(ruleset, state, evt)

    if choice == "approve" and auto_commit_on_consensus and _has_consensus(next_prop, votes):
        commit_res = commit_time_skip(ruleset, cur_state, actor_seat_id=seat_id)
        emitted.extend(commit_res.events)
        return TimeSkipTransitionResult(
            state=commit_res.state,
            events=tuple(emitted),
            proposal=commit_res.proposal,
            completed_activities=commit_res.completed_activities,
            elapsed_seconds_advanced=commit_res.elapsed_seconds_advanced,
        )

    return TimeSkipTransitionResult(
        state=cur_state,
        events=tuple(emitted),
        proposal=cur_state.pending_time_skip,
    )


def interrupt_time_skip(
    ruleset: RulesetSchema,
    state: SceneState,
    elapsed_before_interrupt: int,
    *,
    reason: str,
    actor_seat_id: str = "gm",
) -> TimeSkipTransitionResult:
    """Interrupt a skip after partial elapsed seconds, pausing interruptible tasks cleanly."""
    if elapsed_before_interrupt < 0:
        raise ValueError("elapsed_before_interrupt must be >= 0.")

    emitted: list[VmEvent] = []
    cur_state = state
    completed_list: list[ActiveTimedActivity] = []
    if elapsed_before_interrupt > 0:
        adv_res = advance_world_time(
            ruleset,
            cur_state,
            elapsed_before_interrupt,
            actor_seat_id=actor_seat_id,
            reason=reason,
        )
        cur_state = adv_res.state
        emitted.extend(adv_res.events)
        completed_list.extend(adv_res.completed_activities)

    paused_entities: list[ActiveTimedActivity] = []
    for eid in sorted(cur_state.active_timed_activities):
        act = cur_state.active_timed_activities[eid]
        if act.status == "in_progress" and act.interruptible:
            paused_act = act.model_copy(update={"status": "paused"})
            pause_evt = VmEvent(
                event_id=_next_event_id(cur_state),
                event_type="TIMED_ACTIVITY_UPDATED",
                actor_id=actor_seat_id,
                payload={
                    "entity_id": eid,
                    "op": "upsert",
                    "activity": paused_act.model_dump(mode="json"),
                },
            )
            emitted.append(pause_evt)
            cur_state = apply_event(ruleset, cur_state, pause_evt)
            paused_entities.append(paused_act)

    for paused_act in paused_entities:
        hook_actor = paused_act.entity_id if paused_act.entity_id in cur_state.entities else None
        cur_state, act_hooks = trigger_event_hooks(
            ruleset,
            cur_state,
            event_name="on_timed_activity_interrupted",
            actor_id=hook_actor,
            event_data={
                "activity_id": paused_act.activity_id,
                "entity_id": paused_act.entity_id,
                "label": paused_act.label,
                "elapsed_seconds": paused_act.elapsed_seconds,
                "remaining_seconds": paused_act.remaining_seconds,
                "reason": reason,
            },
        )
        emitted.extend(act_hooks)

    prop = cur_state.pending_time_skip
    if prop is not None:
        next_elapsed = min(prop.duration_seconds, prop.elapsed_seconds + elapsed_before_interrupt)
        interrupted_prop = prop.model_copy(
            update={
                "status": "interrupted",
                "elapsed_seconds": next_elapsed,
                "interrupted_reason": reason,
            }
        )
        upd_evt = VmEvent(
            event_id=_next_event_id(cur_state),
            event_type="TIME_SKIP_UPDATED",
            actor_id=actor_seat_id,
            payload={"proposal": interrupted_prop.model_dump(mode="json")},
        )
        emitted.append(upd_evt)
        cur_state = apply_event(ruleset, cur_state, upd_evt)

        hook_actor = (
            prop.proposer_entity_id if prop.proposer_entity_id in cur_state.entities else None
        )
        cur_state, prop_hooks = trigger_event_hooks(
            ruleset,
            cur_state,
            event_name="on_time_skip_interrupted",
            actor_id=hook_actor,
            event_data={
                "proposal_id": prop.proposal_id,
                "label": prop.label,
                "elapsed_before_interrupt": elapsed_before_interrupt,
                "reason": reason,
            },
        )
        emitted.extend(prop_hooks)

    return TimeSkipTransitionResult(
        state=cur_state,
        events=tuple(emitted),
        proposal=cur_state.pending_time_skip,
        completed_activities=tuple(completed_list),
        elapsed_seconds_advanced=elapsed_before_interrupt,
    )


def gm_trigger_time_skip(
    ruleset: RulesetSchema,
    state: SceneState,
    duration_seconds: int,
    *,
    label: str = "GM Time Skip",
    gm_seat_id: str,
    seat_role: SeatRole = "gm",
    prompt_players: bool = False,
    required_voter_seat_ids: Sequence[str] = (),
    proposer_entity_id: str = "gm",
) -> TimeSkipTransitionResult:
    """Allow an authorized GM/Co-GM/Host to manually advance time or prompt a player vote."""
    if seat_role not in {"gm", "co_gm", "host"}:
        raise PermissionError(
            f"Seat role '{seat_role}' is not authorized to manually trigger time skips."
        )
    if duration_seconds < 1:
        raise ValueError("duration_seconds must be >= 1.")

    if prompt_players:
        return propose_time_skip(
            ruleset,
            state,
            proposer_entity_id,
            label,
            duration_seconds,
            proposer_seat_id=gm_seat_id,
            required_voter_seat_ids=required_voter_seat_ids,
            consensus_mode="unanimous",
            auto_commit_if_solo=False,
        )

    emitted: list[VmEvent] = []
    cur_state = state
    if cur_state.pending_time_skip is not None and cur_state.pending_time_skip.status in {
        "open",
        "held",
    }:
        clear_evt = VmEvent(
            event_id=_next_event_id(cur_state),
            event_type="TIME_SKIP_UPDATED",
            actor_id=gm_seat_id,
            payload={"proposal": None, "superseded_by": gm_seat_id},
        )
        emitted.append(clear_evt)
        cur_state = apply_event(ruleset, cur_state, clear_evt)

    adv_res = advance_world_time(
        ruleset,
        cur_state,
        duration_seconds,
        actor_seat_id=gm_seat_id,
        reason=label,
    )
    emitted.extend(adv_res.events)
    return TimeSkipTransitionResult(
        state=adv_res.state,
        events=tuple(emitted),
        completed_activities=adv_res.completed_activities,
        elapsed_seconds_advanced=adv_res.elapsed_seconds_advanced,
    )


def resolve_cross_branch_comm_delivery_mode(
    same_timeline: bool,
    medium_topology: str,
) -> Literal["live_synchronous", "queue_until_settlement"]:
    """Prevent cross-timeline spoilers by queuing cross-branch comms until settlement."""
    _ = medium_topology
    if same_timeline:
        return "live_synchronous"
    return "queue_until_settlement"
