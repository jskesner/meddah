"""Universal Ruleset-Interpreting Covert Operations (Stealth, Theft & Disguises — ADR-0134)."""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from app.ruleset_vm.blocks import (
    CovertPillar,
    DisguisePillarConfig,
    PvpCovertPolicy,
    RulesetSchema,
    StealthPillarConfig,
    TheftPillarConfig,
)
from app.ruleset_vm.inventory_graph import ProvenanceState, compute_visible_appearance
from app.ruleset_vm.module_registry import MeddahModuleManifest, ModuleProvides
from app.ruleset_vm.time_skip import propose_time_skip as open_time_skip_proposal
from app.ruleset_vm.time_skip import start_timed_activity
from app.ruleset_vm.vm import (
    ActiveDisguiseState,
    ActiveTimedActivity,
    DisguisePreset,
    DisguiseSource,
    PendingMissingItemNotice,
    SceneState,
    TimeSkipProposal,
    VmEvent,
    apply_event,
    is_pvp_covert_blocked,
    resolve_awareness_level,
    resolve_target_visibility,
    trigger_event_hooks,
)

MODULE_MANIFEST = MeddahModuleManifest(
    module_id="covert_ops",
    spec_section="1.1.4B",
    label="Ruleset-Interpreting Covert Operations (Stealth, Theft & Disguises)",
    requires_any_primitive=("covert_stealth", "covert_theft", "covert_disguise"),
    provides=ModuleProvides(
        commands=("hide", "sneak", "steal", "plant", "disguise"),
        ui_panels=("awareness_indicator", "disguise_badge", "disguise_wardrobe"),
        event_hooks=(
            "on_awareness_changed",
            "on_stealth_noise",
            "on_item_stolen",
            "on_item_planted",
            "on_missing_item_noticed",
            "on_disguise_applied",
            "on_disguise_scrutinized",
            "on_disguise_blown",
        ),
        schema_blocks=(
            "CovertOpsConfigBlock",
            "ActiveDisguiseState",
            "DisguisePreset",
            "PendingMissingItemNotice",
        ),
    ),
    scope="campaign",
    ai_dependency="none",
)

COVERT_OPS_MODULE_MANIFEST = MODULE_MANIFEST


class CovertTransitionResult(BaseModel):
    """Audit-complete result of an awareness, theft, provenance, or disguise VM transition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    state: SceneState
    events: tuple[VmEvent, ...]
    awareness_level: str | None = None
    active_disguise: ActiveDisguiseState | None = None
    transferred_item_id: str | None = None
    triggered_notices: tuple[PendingMissingItemNotice, ...] = ()
    saved_preset: DisguisePreset | None = None
    started_activity: ActiveTimedActivity | None = None
    proposed_time_skip: TimeSkipProposal | None = None


class PerceivedIdentityView(BaseModel):
    """Per-observer identity snapshot composing disguises, apparel layers, and forms."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    target_entity_id: str
    observer_entity_id: str | None = None
    perceived_name: str
    perceived_alias_id: str | None = None
    is_disguised: bool = False
    seen_through: bool = False
    presented_tags: tuple[str, ...] = ()
    concealed_item_ids: tuple[str, ...] = ()
    portrait_override_ref: str | None = None
    token_override_ref: str | None = None


def _next_event_id(state: SceneState) -> str:
    return f"evt_{state.scene_id}_{state.event_seq + 1:06d}"


def active_covert_pillars(ruleset: RulesetSchema) -> tuple[CovertPillar, ...]:
    """Return ruleset-declared active covert pillars (empty tuple when dormant)."""
    if ruleset.covert_ops is None:
        return ()
    return ruleset.covert_ops.active_pillars()


def is_pillar_active(ruleset: RulesetSchema, pillar: CovertPillar) -> bool:
    """Return True if the specified covert pillar is declared in the active ruleset."""
    return pillar in active_covert_pillars(ruleset)


def _require_pillar(ruleset: RulesetSchema, pillar: CovertPillar) -> None:
    if not is_pillar_active(ruleset, pillar):
        raise PermissionError(
            f"Covert pillar '{pillar}' is dormant in ruleset '{ruleset.manifest.package_id}'."
        )


def _stealth_cfg(ruleset: RulesetSchema) -> StealthPillarConfig:
    _require_pillar(ruleset, "stealth")
    assert ruleset.covert_ops is not None
    assert ruleset.covert_ops.stealth is not None
    return ruleset.covert_ops.stealth


def _theft_cfg(ruleset: RulesetSchema) -> TheftPillarConfig:
    _require_pillar(ruleset, "theft")
    assert ruleset.covert_ops is not None
    assert ruleset.covert_ops.theft is not None
    return ruleset.covert_ops.theft


def _disguise_cfg(ruleset: RulesetSchema) -> DisguisePillarConfig:
    _require_pillar(ruleset, "disguise")
    assert ruleset.covert_ops is not None
    assert ruleset.covert_ops.disguise is not None
    return ruleset.covert_ops.disguise


def check_pvp_covert_allowed(
    state: SceneState,
    actor_id: str,
    target_id: str,
    *,
    gm_approved: bool = False,
) -> tuple[bool, str | None]:
    """Validate whether host pvp_covert_policy permits actor->target covert action."""
    if is_pvp_covert_blocked(state, actor_id, target_id, gm_approved=gm_approved):
        return (
            False,
            f"PC-to-PC covert action blocked by pvp_covert_policy='{state.pvp_covert_policy}'.",
        )
    return True, None


def set_pvp_covert_policy(
    ruleset: RulesetSchema,
    state: SceneState,
    policy: PvpCovertPolicy,
    *,
    actor_seat_id: str,
    reason: str = "",
) -> CovertTransitionResult:
    """Update host-authoritative PvP covert policy and commit an audited replay event."""
    evt = VmEvent(
        event_id=_next_event_id(state),
        event_type="COVERT_POLICY_UPDATED",
        actor_id=actor_seat_id,
        payload={"pvp_covert_policy": policy, "reason": reason},
    )
    next_state = apply_event(ruleset, state, evt)
    return CovertTransitionResult(state=next_state, events=(evt,))


def get_awareness_level(
    ruleset: RulesetSchema,
    state: SceneState,
    observer_id: str,
    target_id: str,
) -> str:
    """Return observer's current awareness level toward target without mutating rulesets."""
    return resolve_awareness_level(ruleset, state, observer_id, target_id)


def set_awareness_level(
    ruleset: RulesetSchema,
    state: SceneState,
    observer_id: str,
    target_id: str,
    level: str,
    *,
    actor_seat_id: str | None = None,
    gm_approved: bool = False,
    bypass_pvp_policy: bool = False,
) -> CovertTransitionResult:
    """Set observer->target awareness level, respecting ruleset levels and PvP policy."""
    st_cfg = _stealth_cfg(ruleset)
    if observer_id not in state.entities:
        raise KeyError(f"Unknown observer entity '{observer_id}'")
    if target_id not in state.entities:
        raise KeyError(f"Unknown target entity '{target_id}'")
    if level not in st_cfg.awareness_levels:
        raise ValueError(
            f"Unknown awareness level '{level}'; expected one of {st_cfg.awareness_levels}."
        )
    if not bypass_pvp_policy:
        allowed, reason = check_pvp_covert_allowed(
            state, observer_id, target_id, gm_approved=gm_approved
        )
        if not allowed:
            raise PermissionError(reason or "PvP covert awareness check denied.")

    prev_level = get_awareness_level(ruleset, state, observer_id, target_id)
    actor = actor_seat_id or observer_id
    emitted: list[VmEvent] = []

    evt = VmEvent(
        event_id=_next_event_id(state),
        event_type="AWARENESS_CHANGED",
        actor_id=actor,
        payload={
            "observer_id": observer_id,
            "target_id": target_id,
            "level": level,
            "previous_level": prev_level,
        },
    )
    emitted.append(evt)
    cur_state = apply_event(ruleset, state, evt)

    if st_cfg.sync_hidden_condition_on_detect and level == st_cfg.detected_level:
        target_ent = cur_state.entities[target_id]
        for cond_id in st_cfg.hidden_condition_ids:
            if cond_id in target_ent.conditions:
                cond_evt = VmEvent(
                    event_id=_next_event_id(cur_state),
                    event_type="CONDITION_CHANGED",
                    actor_id=actor,
                    payload={
                        "entity_id": target_id,
                        "op": "remove",
                        "condition_id": cond_id,
                        "duration_turns": None,
                    },
                )
                emitted.append(cond_evt)
                cur_state = apply_event(ruleset, cur_state, cond_evt)

    cur_state, hook_events = trigger_event_hooks(
        ruleset,
        cur_state,
        event_name="on_awareness_changed",
        actor_id=observer_id,
        target_id=target_id,
        event_data={
            "observer_id": observer_id,
            "target_id": target_id,
            "level": level,
            "previous_level": prev_level,
            "source_entity_id": actor,
        },
    )
    emitted.extend(hook_events)
    return CovertTransitionResult(
        state=cur_state,
        events=tuple(emitted),
        awareness_level=level,
    )


def is_target_visible_to_observer(
    ruleset: RulesetSchema,
    state: SceneState,
    observer_id: str,
    target_id: str,
) -> bool:
    """Return True if target is visible to observer using stealth levels and bypass tags."""
    return resolve_target_visibility(ruleset, state, observer_id, target_id)


def notify_stealth_noise(
    ruleset: RulesetSchema,
    state: SceneState,
    actor_id: str,
    *,
    source: str = "comms_bleed",
    detail: str = "",
) -> CovertTransitionResult:
    """Fire ruleset on_stealth_noise hooks when acoustic/action noise affects a stealth actor."""
    _stealth_cfg(ruleset)
    if actor_id not in state.entities:
        raise KeyError(f"Unknown actor entity '{actor_id}'")
    next_state, hook_events = trigger_event_hooks(
        ruleset,
        state,
        event_name="on_stealth_noise",
        actor_id=actor_id,
        target_id=None,
        event_data={
            "entity_id": actor_id,
            "source": source,
            "detail": detail,
        },
    )
    return CovertTransitionResult(state=next_state, events=hook_events)


def set_stealth_score(
    ruleset: RulesetSchema,
    state: SceneState,
    entity_id: str,
    score: int | float | None,
    *,
    actor_seat_id: str | None = None,
) -> CovertTransitionResult:
    """Update an entity's cached stealth_score deterministically when stealth pillar is active."""
    _stealth_cfg(ruleset)
    if entity_id not in state.entities:
        raise KeyError(f"Unknown entity '{entity_id}'")
    evt = VmEvent(
        event_id=_next_event_id(state),
        event_type="STEALTH_SCORE_UPDATED",
        actor_id=actor_seat_id or entity_id,
        payload={"entity_id": entity_id, "stealth_score": score},
    )
    next_state = apply_event(ruleset, state, evt)
    return CovertTransitionResult(state=next_state, events=(evt,))


def _tag_for_provenance(
    theft_cfg: TheftPillarConfig,
    provenance_state: ProvenanceState | None,
) -> str | None:
    if provenance_state == "stolen":
        return theft_cfg.stolen_tag
    if provenance_state == "planted":
        return theft_cfg.planted_tag
    if provenance_state == "contraband":
        return theft_cfg.contraband_tag
    return None


def transfer_scene_item(
    ruleset: RulesetSchema,
    state: SceneState,
    from_entity_id: str,
    to_entity_id: str,
    item_id: str,
    *,
    target_container_id: str | None = None,
    provenance_state: ProvenanceState | None = "stolen",
    origin_jurisdiction_id: str | None = None,
    notice_delay_turns: int | None = None,
    actor_seat_id: str | None = None,
    gm_approved: bool = False,
    bypass_pvp_policy: bool = False,
) -> CovertTransitionResult:
    """Atomically transfer an inventory item between entities with provenance & notice hooks."""
    th_cfg = _theft_cfg(ruleset)
    if from_entity_id == to_entity_id:
        raise ValueError("from_entity_id and to_entity_id must differ.")
    if from_entity_id not in state.entities:
        raise KeyError(f"Unknown source entity '{from_entity_id}'")
    if to_entity_id not in state.entities:
        raise KeyError(f"Unknown destination entity '{to_entity_id}'")
    src_inv = state.entity_inventories.get(from_entity_id)
    if src_inv is None or item_id not in src_inv.items:
        raise KeyError(f"Item '{item_id}' not found in '{from_entity_id}' inventory.")

    actor = actor_seat_id or to_entity_id
    other_party = from_entity_id if actor != from_entity_id else to_entity_id
    if not bypass_pvp_policy:
        allowed, reason = check_pvp_covert_allowed(
            state, actor, other_party, gm_approved=gm_approved
        )
        if not allowed:
            raise PermissionError(reason or "PvP covert item transfer denied.")

    item_node = src_inv.items[item_id]
    eff_jurisdiction = (
        origin_jurisdiction_id
        if origin_jurisdiction_id is not None
        else item_node.origin_jurisdiction_id
    )
    eff_delay = (
        notice_delay_turns
        if notice_delay_turns is not None
        else (th_cfg.default_notice_delay_turns if provenance_state == "stolen" else None)
    )
    notice_payload: dict[str, object] | None = None
    if eff_delay is not None and eff_delay >= 1 and provenance_state == "stolen":
        notice_payload = PendingMissingItemNotice(
            notice_id=f"notice_{state.scene_id}_{state.event_seq + 1:06d}_{item_id}",
            victim_entity_id=from_entity_id,
            thief_entity_id=to_entity_id,
            item_id=item_id,
            item_name=item_node.name,
            remaining_turns=eff_delay,
            origin_jurisdiction_id=eff_jurisdiction,
        ).model_dump(mode="json")

    evt = VmEvent(
        event_id=_next_event_id(state),
        event_type="ITEM_TRANSFERRED",
        actor_id=actor,
        payload={
            "from_entity_id": from_entity_id,
            "to_entity_id": to_entity_id,
            "item_id": item_id,
            "target_container_id": target_container_id,
            "provenance_state": provenance_state,
            "stolen_from_entity_id": from_entity_id if provenance_state == "stolen" else None,
            "origin_jurisdiction_id": eff_jurisdiction,
            "provenance_tag": _tag_for_provenance(th_cfg, provenance_state),
            "notice": notice_payload,
        },
    )
    emitted: list[VmEvent] = [evt]
    cur_state = apply_event(ruleset, state, evt)

    if provenance_state == "stolen":
        cur_state, hook_events = trigger_event_hooks(
            ruleset,
            cur_state,
            event_name="on_item_stolen",
            actor_id=to_entity_id,
            target_id=from_entity_id,
            event_data={
                "thief_entity_id": to_entity_id,
                "victim_entity_id": from_entity_id,
                "item_id": item_id,
                "item_name": item_node.name,
            },
        )
        emitted.extend(hook_events)
    elif provenance_state == "planted":
        cur_state, hook_events = trigger_event_hooks(
            ruleset,
            cur_state,
            event_name="on_item_planted",
            actor_id=from_entity_id,
            target_id=to_entity_id,
            event_data={
                "planter_entity_id": from_entity_id,
                "target_entity_id": to_entity_id,
                "item_id": item_id,
                "item_name": item_node.name,
            },
        )
        emitted.extend(hook_events)

    return CovertTransitionResult(
        state=cur_state,
        events=tuple(emitted),
        transferred_item_id=item_id,
    )


def mark_scene_item_provenance(
    ruleset: RulesetSchema,
    state: SceneState,
    entity_id: str,
    item_id: str,
    provenance_state: ProvenanceState,
    *,
    owner_entity_id: str | None = None,
    origin_jurisdiction_id: str | None = None,
    stolen_from_entity_id: str | None = None,
    actor_seat_id: str | None = None,
) -> CovertTransitionResult:
    """Update legal/stolen/planted/contraband provenance on a carried item (e.g. fencing)."""
    th_cfg = _theft_cfg(ruleset)
    if entity_id not in state.entities:
        raise KeyError(f"Unknown entity '{entity_id}'")
    inv = state.entity_inventories.get(entity_id)
    if inv is None or item_id not in inv.items:
        raise KeyError(f"Item '{item_id}' not found in '{entity_id}' inventory.")

    tag_to_add = _tag_for_provenance(th_cfg, provenance_state)
    rem_tags = (
        (th_cfg.stolen_tag, th_cfg.planted_tag, th_cfg.contraband_tag)
        if provenance_state == "legitimate"
        else ()
    )
    evt = VmEvent(
        event_id=_next_event_id(state),
        event_type="ITEM_PROVENANCE_CHANGED",
        actor_id=actor_seat_id or entity_id,
        payload={
            "entity_id": entity_id,
            "item_id": item_id,
            "provenance_state": provenance_state,
            "owner_entity_id": owner_entity_id,
            "origin_jurisdiction_id": origin_jurisdiction_id,
            "stolen_from_entity_id": stolen_from_entity_id,
            "tag_to_add": tag_to_add,
            "tags_to_remove": list(rem_tags),
        },
    )
    next_state = apply_event(ruleset, state, evt)
    return CovertTransitionResult(
        state=next_state,
        events=(evt,),
        transferred_item_id=item_id,
    )


def tick_missing_item_notices(
    ruleset: RulesetSchema,
    state: SceneState,
    *,
    turns: int = 1,
    actor_seat_id: str | None = None,
) -> CovertTransitionResult:
    """Advance delayed missing-item discovery counters and fire on_missing_item_noticed."""
    if turns < 1:
        raise ValueError("turns must be >= 1.")
    if not is_pillar_active(ruleset, "theft") or not state.pending_missing_notices:
        return CovertTransitionResult(state=state, events=())

    triggered = tuple(
        notice for notice in state.pending_missing_notices if notice.remaining_turns - turns <= 0
    )
    tick_evt = VmEvent(
        event_id=_next_event_id(state),
        event_type="MISSING_NOTICE_TICKED",
        actor_id=actor_seat_id or "system",
        payload={"turns": turns},
    )
    emitted: list[VmEvent] = [tick_evt]
    cur_state = apply_event(ruleset, state, tick_evt)

    for notice in triggered:
        if notice.victim_entity_id not in cur_state.entities:
            continue
        tgt = notice.thief_entity_id if notice.thief_entity_id in cur_state.entities else None
        cur_state, hook_events = trigger_event_hooks(
            ruleset,
            cur_state,
            event_name="on_missing_item_noticed",
            actor_id=notice.victim_entity_id,
            target_id=tgt,
            event_data={
                "notice_id": notice.notice_id,
                "victim_entity_id": notice.victim_entity_id,
                "thief_entity_id": notice.thief_entity_id,
                "item_id": notice.item_id,
                "item_name": notice.item_name,
                "origin_jurisdiction_id": notice.origin_jurisdiction_id,
            },
        )
        emitted.extend(hook_events)

    return CovertTransitionResult(
        state=cur_state,
        events=tuple(emitted),
        triggered_notices=triggered,
    )


def apply_disguise(
    ruleset: RulesetSchema,
    state: SceneState,
    entity_id: str,
    alias_id: str,
    presented_name: str,
    *,
    presented_tags: Sequence[str] = (),
    disguise_source: DisguiseSource = "kit",
    quality_score: int | float | None = None,
    voice_disguised: bool = False,
    portrait_override_ref: str | None = None,
    token_override_ref: str | None = None,
    actor_seat_id: str | None = None,
) -> CovertTransitionResult:
    """Equip a non-stat ActiveDisguiseState persona overlay onto an entity."""
    _require_pillar(ruleset, "disguise")
    if entity_id not in state.entities:
        raise KeyError(f"Unknown entity '{entity_id}'")

    disguise = ActiveDisguiseState(
        alias_id=alias_id,
        presented_name=presented_name,
        presented_tags=tuple(sorted(set(presented_tags))),
        disguise_source=disguise_source,
        quality_score=quality_score,
        voice_disguised=voice_disguised,
        portrait_override_ref=portrait_override_ref,
        token_override_ref=token_override_ref,
    )
    evt = VmEvent(
        event_id=_next_event_id(state),
        event_type="DISGUISE_CHANGED",
        actor_id=actor_seat_id or entity_id,
        payload={
            "entity_id": entity_id,
            "op": "apply",
            "active_disguise": disguise.model_dump(mode="json"),
        },
    )
    emitted: list[VmEvent] = [evt]
    cur_state = apply_event(ruleset, state, evt)

    cur_state, hook_events = trigger_event_hooks(
        ruleset,
        cur_state,
        event_name="on_disguise_applied",
        actor_id=entity_id,
        event_data={
            "entity_id": entity_id,
            "alias_id": alias_id,
            "presented_name": presented_name,
            "quality_score": quality_score,
            "disguise_source": disguise_source,
        },
    )
    emitted.extend(hook_events)
    final_disguise = cur_state.entities[entity_id].active_disguise
    return CovertTransitionResult(
        state=cur_state,
        events=tuple(emitted),
        active_disguise=final_disguise,
    )


def mark_disguise_seen_through(
    ruleset: RulesetSchema,
    state: SceneState,
    observer_id: str,
    target_id: str,
    *,
    actor_seat_id: str | None = None,
    gm_approved: bool = False,
    bypass_pvp_policy: bool = False,
) -> CovertTransitionResult:
    """Record that a specific observer saw through target's active disguise."""
    _require_pillar(ruleset, "disguise")
    if observer_id not in state.entities:
        raise KeyError(f"Unknown observer entity '{observer_id}'")
    if target_id not in state.entities:
        raise KeyError(f"Unknown target entity '{target_id}'")
    if not bypass_pvp_policy:
        allowed, reason = check_pvp_covert_allowed(
            state, observer_id, target_id, gm_approved=gm_approved
        )
        if not allowed:
            raise PermissionError(reason or "PvP disguise scrutiny denied.")

    target_ent = state.entities[target_id]
    if target_ent.active_disguise is None:
        return CovertTransitionResult(state=state, events=(), active_disguise=None)

    prev_alias = target_ent.active_disguise.alias_id
    evt = VmEvent(
        event_id=_next_event_id(state),
        event_type="DISGUISE_CHANGED",
        actor_id=actor_seat_id or observer_id,
        payload={
            "entity_id": target_id,
            "op": "seen_through",
            "observer_id": observer_id,
            "alias_id": prev_alias,
        },
    )
    emitted: list[VmEvent] = [evt]
    cur_state = apply_event(ruleset, state, evt)
    cur_state, hook_events = trigger_event_hooks(
        ruleset,
        cur_state,
        event_name="on_disguise_scrutinized",
        actor_id=observer_id,
        target_id=target_id,
        event_data={
            "observer_id": observer_id,
            "target_id": target_id,
            "alias_id": prev_alias,
            "reason": "seen_through",
        },
    )
    emitted.extend(hook_events)
    return CovertTransitionResult(
        state=cur_state,
        events=tuple(emitted),
        active_disguise=cur_state.entities[target_id].active_disguise,
    )


def blow_disguise(
    ruleset: RulesetSchema,
    state: SceneState,
    entity_id: str,
    *,
    reason: str = "manual_remove",
    revealed_by_id: str | None = None,
    actor_seat_id: str | None = None,
) -> CovertTransitionResult:
    """Publicly clear/blow an entity's active disguise and fire on_disguise_blown."""
    _require_pillar(ruleset, "disguise")
    if entity_id not in state.entities:
        raise KeyError(f"Unknown entity '{entity_id}'")
    ent = state.entities[entity_id]
    if ent.active_disguise is None:
        return CovertTransitionResult(state=state, events=(), active_disguise=None)

    prev_alias = ent.active_disguise.alias_id
    evt = VmEvent(
        event_id=_next_event_id(state),
        event_type="DISGUISE_CHANGED",
        actor_id=actor_seat_id or revealed_by_id or entity_id,
        payload={
            "entity_id": entity_id,
            "op": "blow",
            "alias_id": prev_alias,
            "reason": reason,
        },
    )
    emitted: list[VmEvent] = [evt]
    cur_state = apply_event(ruleset, state, evt)
    valid_revealer = revealed_by_id if revealed_by_id in cur_state.entities else None
    cur_state, hook_events = trigger_event_hooks(
        ruleset,
        cur_state,
        event_name="on_disguise_blown",
        actor_id=entity_id,
        target_id=valid_revealer,
        event_data={
            "entity_id": entity_id,
            "alias_id": prev_alias,
            "reason": reason,
            "revealed_by_id": revealed_by_id,
        },
    )
    emitted.extend(hook_events)
    return CovertTransitionResult(
        state=cur_state,
        events=tuple(emitted),
        active_disguise=cur_state.entities[entity_id].active_disguise,
    )


def resolve_perceived_identity(
    ruleset: RulesetSchema,
    state: SceneState,
    target_id: str,
    *,
    observer_id: str | None = None,
) -> PerceivedIdentityView:
    """Compute how an observer perceives target's name, persona tags, apparel & overrides."""
    if target_id not in state.entities:
        raise KeyError(f"Unknown target entity '{target_id}'")
    target_ent = state.entities[target_id]
    inv = state.entity_inventories.get(target_id)
    appearance = compute_visible_appearance(inv) if inv is not None else None
    concealed = appearance.concealed_item_ids if appearance is not None else ()
    apparel_tags: set[str] = (
        set(appearance.active_appearance_tags) if appearance is not None else set()
    )

    form_def = (
        ruleset.forms.get(target_ent.active_form.form_id)
        if target_ent.active_form is not None
        else None
    )
    form_portrait = form_def.portrait_override_ref if form_def is not None else None
    form_token = form_def.token_override_ref if form_def is not None else None

    disguise = target_ent.active_disguise if is_pillar_active(ruleset, "disguise") else None
    if disguise is None:
        return PerceivedIdentityView(
            target_entity_id=target_id,
            observer_entity_id=observer_id,
            perceived_name=target_ent.name,
            perceived_alias_id=None,
            is_disguised=False,
            seen_through=False,
            presented_tags=tuple(sorted(apparel_tags)),
            concealed_item_ids=concealed,
            portrait_override_ref=form_portrait,
            token_override_ref=form_token,
        )

    seen_through = observer_id is not None and observer_id in disguise.seen_through_by
    if seen_through:
        return PerceivedIdentityView(
            target_entity_id=target_id,
            observer_entity_id=observer_id,
            perceived_name=target_ent.name,
            perceived_alias_id=None,
            is_disguised=True,
            seen_through=True,
            presented_tags=tuple(sorted(apparel_tags)),
            concealed_item_ids=concealed,
            portrait_override_ref=form_portrait,
            token_override_ref=form_token,
        )

    return PerceivedIdentityView(
        target_entity_id=target_id,
        observer_entity_id=observer_id,
        perceived_name=disguise.presented_name,
        perceived_alias_id=disguise.alias_id,
        is_disguised=True,
        seen_through=False,
        presented_tags=tuple(sorted(apparel_tags | set(disguise.presented_tags))),
        concealed_item_ids=concealed,
        portrait_override_ref=disguise.portrait_override_ref or form_portrait,
        token_override_ref=disguise.token_override_ref or form_token,
    )


def check_speech_disguise_scrutiny(
    ruleset: RulesetSchema,
    state: SceneState,
    speaker_id: str,
    observer_ids: Sequence[str],
    *,
    voice_modulated: bool = False,
    gm_approved: bool = False,
) -> CovertTransitionResult:
    """Fire ruleset scrutiny hooks when a disguised speaker talks without voice modulation."""
    dg_cfg = _disguise_cfg(ruleset)
    if speaker_id not in state.entities:
        raise KeyError(f"Unknown speaker entity '{speaker_id}'")

    speaker = state.entities[speaker_id]
    if speaker.active_disguise is None or not dg_cfg.requires_voice_modulation_for_speech:
        return CovertTransitionResult(
            state=state, events=(), active_disguise=speaker.active_disguise
        )
    if voice_modulated or speaker.active_disguise.voice_disguised:
        return CovertTransitionResult(
            state=state, events=(), active_disguise=speaker.active_disguise
        )

    cur_state = state
    emitted: list[VmEvent] = []
    disguise = speaker.active_disguise
    for obs_id in sorted(set(observer_ids)):
        if obs_id == speaker_id or obs_id not in cur_state.entities:
            continue
        if is_pvp_covert_blocked(cur_state, obs_id, speaker_id, gm_approved=gm_approved):
            continue
        cur_state, hook_events = trigger_event_hooks(
            ruleset,
            cur_state,
            event_name="on_disguise_scrutinized",
            actor_id=obs_id,
            target_id=speaker_id,
            event_data={
                "observer_id": obs_id,
                "target_id": speaker_id,
                "alias_id": disguise.alias_id,
                "quality_score": disguise.quality_score or 0,
                "reason": "unmodulated_speech",
            },
        )
        emitted.extend(hook_events)

    return CovertTransitionResult(
        state=cur_state,
        events=tuple(emitted),
        active_disguise=cur_state.entities[speaker_id].active_disguise,
    )


def list_disguise_presets(state: SceneState, entity_id: str) -> tuple[DisguisePreset, ...]:
    """List saved registered disguise slots for an entity in deterministic preset_id order."""
    if entity_id not in state.entities:
        raise KeyError(f"Unknown entity '{entity_id}'")
    presets = state.entities[entity_id].disguise_presets
    return tuple(presets[pid] for pid in sorted(presets))


def save_disguise_preset(
    ruleset: RulesetSchema,
    state: SceneState,
    entity_id: str,
    preset: DisguisePreset,
    *,
    actor_seat_id: str | None = None,
) -> CovertTransitionResult:
    """Save or overwrite a registered DisguisePreset slot on an entity."""
    _require_pillar(ruleset, "disguise")
    if entity_id not in state.entities:
        raise KeyError(f"Unknown entity '{entity_id}'")
    if preset.don_action_id is not None and preset.don_action_id not in ruleset.actions:
        raise KeyError(f"Unknown don_action_id '{preset.don_action_id}' in ruleset.")
    if preset.outfit_preset_id is not None:
        inv = state.entity_inventories.get(entity_id)
        if inv is None or preset.outfit_preset_id not in inv.outfit_presets:
            raise KeyError(
                f"Unknown outfit_preset_id '{preset.outfit_preset_id}' for entity '{entity_id}'."
            )

    evt = VmEvent(
        event_id=_next_event_id(state),
        event_type="DISGUISE_PRESET_UPDATED",
        actor_id=actor_seat_id or entity_id,
        payload={
            "entity_id": entity_id,
            "op": "save",
            "preset": preset.model_dump(mode="json"),
        },
    )
    next_state = apply_event(ruleset, state, evt)
    saved = next_state.entities[entity_id].disguise_presets[preset.preset_id]
    return CovertTransitionResult(
        state=next_state,
        events=(evt,),
        saved_preset=saved,
    )


def delete_disguise_preset(
    ruleset: RulesetSchema,
    state: SceneState,
    entity_id: str,
    preset_id: str,
    *,
    actor_seat_id: str | None = None,
) -> CovertTransitionResult:
    """Delete a registered DisguisePreset slot from an entity."""
    _require_pillar(ruleset, "disguise")
    if entity_id not in state.entities:
        raise KeyError(f"Unknown entity '{entity_id}'")
    if preset_id not in state.entities[entity_id].disguise_presets:
        raise KeyError(f"Unknown disguise preset '{preset_id}' on entity '{entity_id}'.")

    evt = VmEvent(
        event_id=_next_event_id(state),
        event_type="DISGUISE_PRESET_UPDATED",
        actor_id=actor_seat_id or entity_id,
        payload={"entity_id": entity_id, "op": "delete", "preset_id": preset_id},
    )
    next_state = apply_event(ruleset, state, evt)
    return CovertTransitionResult(state=next_state, events=(evt,))


def resolve_disguise_don_duration(ruleset: RulesetSchema, preset: DisguisePreset) -> int | None:
    """Resolve ruleset/preset donning duration in seconds (None when instant/unspecified)."""
    dg_cfg = _disguise_cfg(ruleset)
    if preset.don_duration_seconds is not None:
        return preset.don_duration_seconds
    if preset.disguise_source in dg_cfg.source_don_durations_seconds:
        return dg_cfg.source_don_durations_seconds[preset.disguise_source]
    return dg_cfg.default_don_duration_seconds


def don_disguise_preset(
    ruleset: RulesetSchema,
    state: SceneState,
    entity_id: str,
    preset_id: str,
    *,
    quality_score: int | float | None = None,
    actor_seat_id: str | None = None,
    immediate: bool = False,
    propose_time_skip: bool = True,
    required_voter_seat_ids: Sequence[str] = (),
    room_id: str | None = None,
    override_duration_seconds: int | None = None,
) -> CovertTransitionResult:
    """Validate and don a DisguisePreset either immediately or via synchronized time skip."""
    _require_pillar(ruleset, "disguise")
    if entity_id not in state.entities:
        raise KeyError(f"Unknown entity '{entity_id}'")
    entity = state.entities[entity_id]
    preset = entity.disguise_presets.get(preset_id)
    if preset is None:
        raise KeyError(f"Unknown disguise preset '{preset_id}' on entity '{entity_id}'.")

    inv = state.entity_inventories.get(entity_id)
    for req_iid in preset.required_item_ids:
        if inv is None or req_iid not in inv.items:
            raise ValueError(
                f"Missing required disguise item '{req_iid}' for preset '{preset_id}'."
            )
    if preset.outfit_preset_id is not None:
        if inv is None or preset.outfit_preset_id not in inv.outfit_presets:
            raise KeyError(
                f"Linked outfit preset '{preset.outfit_preset_id}' is missing on '{entity_id}'."
            )
        outfit = inv.outfit_presets[preset.outfit_preset_id]
        for iid in (*outfit.worn_item_ids, *outfit.equipped_attachments.values()):
            if iid not in inv.items:
                raise ValueError(
                    f"Linked outfit '{preset.outfit_preset_id}' requires missing item '{iid}'."
                )

    duration = (
        override_duration_seconds
        if override_duration_seconds is not None
        else resolve_disguise_don_duration(ruleset, preset)
    )
    if duration is not None and duration > 0 and not immediate:
        act_res = start_timed_activity(
            ruleset,
            state,
            entity_id,
            f"Don disguise: {preset.label}",
            duration,
            category="disguise_don",
            interruptible=True,
            room_id=room_id,
            completion_payload={
                "kind": "apply_disguise_preset",
                "preset_id": preset.preset_id,
                "quality_score": quality_score,
                "outfit_preset_id": preset.outfit_preset_id,
            },
            actor_seat_id=actor_seat_id,
        )
        emitted: list[VmEvent] = list(act_res.events)
        cur_state = act_res.state
        prop_out: TimeSkipProposal | None = None
        if propose_time_skip:
            prop_res = open_time_skip_proposal(
                ruleset,
                cur_state,
                entity_id,
                f"Don disguise: {preset.label}",
                duration,
                proposer_seat_id=actor_seat_id or entity_id,
                required_voter_seat_ids=required_voter_seat_ids,
                auto_commit_if_solo=False,
            )
            cur_state = prop_res.state
            emitted.extend(prop_res.events)
            prop_out = prop_res.proposal
        return CovertTransitionResult(
            state=cur_state,
            events=tuple(emitted),
            saved_preset=preset,
            started_activity=act_res.activity,
            proposed_time_skip=prop_out,
        )

    disguise = ActiveDisguiseState(
        alias_id=preset.alias_id,
        presented_name=preset.presented_name,
        presented_tags=tuple(sorted(set(preset.presented_tags))),
        disguise_source=preset.disguise_source,
        quality_score=quality_score,
        voice_disguised=preset.voice_disguised,
        portrait_override_ref=preset.portrait_override_ref,
        token_override_ref=preset.token_override_ref,
    )
    evt = VmEvent(
        event_id=_next_event_id(state),
        event_type="DISGUISE_CHANGED",
        actor_id=actor_seat_id or entity_id,
        payload={
            "entity_id": entity_id,
            "op": "apply",
            "active_disguise": disguise.model_dump(mode="json"),
            "outfit_preset_id": preset.outfit_preset_id,
            "preset_id": preset.preset_id,
        },
    )
    emitted_imm: list[VmEvent] = [evt]
    cur_state = apply_event(ruleset, state, evt)
    cur_state, hook_events = trigger_event_hooks(
        ruleset,
        cur_state,
        event_name="on_disguise_applied",
        actor_id=entity_id,
        event_data={
            "entity_id": entity_id,
            "alias_id": preset.alias_id,
            "presented_name": preset.presented_name,
            "quality_score": quality_score,
            "disguise_source": preset.disguise_source,
            "preset_id": preset.preset_id,
        },
    )
    emitted_imm.extend(hook_events)
    return CovertTransitionResult(
        state=cur_state,
        events=tuple(emitted_imm),
        active_disguise=cur_state.entities[entity_id].active_disguise,
        saved_preset=preset,
    )
