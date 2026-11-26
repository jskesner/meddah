"""Deterministic Zero-AI Terminal MUD Session Engine backed by the Ruleset VM."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import cast

from app.cli.models import (
    CampaignMetadata,
    CheckpointSummary,
    MudTurnResult,
    RoomNodeSpec,
)
from app.cli.starter_adventure import bootstrap_entities_for_ruleset, build_ashfall_rooms
from app.mud_parser import (
    BUILTIN_EMOTES,
    RoomTopologyEdge,
    parse_mixed_pose,
    parse_mud_command,
    render_emote,
    render_mixed_pose,
    resolve_shout_propagation,
    resolve_whisper_eavesdrop,
)
from app.ruleset_vm import (
    ActionBlock,
    DeterministicRngStream,
    DisguisePreset,
    RandomizerSpec,
    RulesetSchema,
    ScalarValue,
    SceneState,
    SeatRole,
    TimeSkipVoteChoice,
    VmEvent,
    advance_turn,
    advance_world_time,
    apply_disguise,
    apply_event,
    apply_sheet_override,
    blow_disguise,
    compute_entity_view,
    delay_turn,
    don_disguise_preset,
    execute_action,
    gm_trigger_time_skip,
    handoff_spotlight,
    initialize_scene_state,
    interrupt_time_skip,
    is_pillar_active,
    is_target_visible_to_observer,
    list_available_forms,
    list_disguise_presets,
    propose_time_skip,
    replay_events,
    resolve_perceived_identity,
    resolve_randomizer,
    revert_form,
    save_disguise_preset,
    schedule_concurrent_activity,
    set_awareness_level,
    shift_into_form,
    start_round_initiative,
    state_hash,
    transfer_scene_item,
    vote_on_time_skip,
)

_DIR_ALIASES: dict[str, str] = {
    "n": "north",
    "s": "south",
    "e": "east",
    "w": "west",
    "u": "up",
    "d": "down",
    "ne": "northeast",
    "nw": "northwest",
    "se": "southeast",
    "sw": "southwest",
}


def _parse_scalar(raw: str) -> ScalarValue:
    low = raw.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        return raw


def _default_observer_for_room(
    state: SceneState,
    room: RoomNodeSpec,
    entity_rooms: Mapping[str, str],
    actor_id: str,
) -> str | None:
    for eid in sorted(entity_rooms):
        if eid != actor_id and entity_rooms[eid] == room.room_id and eid in state.entities:
            return eid
    for eid in sorted(state.entities):
        if eid != actor_id:
            return eid
    return None


class MudSessionEngine:
    """In-memory deterministic MUD engine bridging terminal/WS commands and the Ruleset VM."""

    def __init__(
        self,
        campaign: CampaignMetadata,
        ruleset: RulesetSchema,
        *,
        rooms: Mapping[str, RoomNodeSpec] | None = None,
        initial_state: SceneState | None = None,
        state: SceneState | None = None,
        event_log: Sequence[VmEvent] = (),
        entity_rooms: Mapping[str, str] | None = None,
        checkpoints: Sequence[CheckpointSummary] = (),
        active_entity_id: str = "pc_lead",
        active_seat_id: str = "seat_host",
        active_seat_role: SeatRole = "gm",
        manual_roll_mode: bool = False,
    ) -> None:
        self.campaign = campaign
        self.ruleset = ruleset
        self.rooms: dict[str, RoomNodeSpec] = dict(rooms or build_ashfall_rooms())

        if initial_state is None:
            entities, inventories = bootstrap_entities_for_ruleset(ruleset)
            init_state = initialize_scene_state(
                ruleset,
                campaign.campaign_id,
                entities,
                scene_seed=campaign.scene_seed,
                entity_inventories=inventories,
            )
            default_rooms: dict[str, str] = {"pc_lead": "ashfall_courtyard"}
            for rm_id, rm in self.rooms.items():
                for npc_id in rm.npc_ids:
                    default_rooms[npc_id] = rm_id
            for eid in sorted(init_state.entities):
                default_rooms.setdefault(eid, "ashfall_courtyard")
        else:
            init_state = initial_state
            default_rooms = dict.fromkeys(init_state.entities, "ashfall_courtyard")

        self.initial_state: SceneState = init_state
        self.event_log: list[VmEvent] = list(event_log)
        self.state: SceneState = (
            state
            if state is not None
            else (
                replay_events(ruleset, init_state, self.event_log) if self.event_log else init_state
            )
        )
        self.entity_rooms: dict[str, str] = (
            dict(entity_rooms) if entity_rooms is not None else default_rooms
        )
        self.checkpoints: list[CheckpointSummary] = list(checkpoints)
        self.active_entity_id = active_entity_id
        self.active_seat_id = active_seat_id
        self.active_seat_role: SeatRole = active_seat_role
        self.manual_roll_mode = manual_roll_mode
        self.pending_manual_action: dict[str, object] | None = None
        self._manual_roll_counter = 0

    def _current_room(self) -> RoomNodeSpec:
        rm_id = self.entity_rooms.get(self.active_entity_id, "ashfall_courtyard")
        return self.rooms[rm_id]

    def _next_event_id(self) -> str:
        return f"evt_{self.state.scene_id}_{self.state.event_seq + 1:06d}"

    def _append_events(self, events: Sequence[VmEvent], next_state: SceneState) -> None:
        self.event_log.extend(events)
        self.state = next_state

    def _apply_new_event(self, event: VmEvent) -> SceneState:
        next_state = apply_event(self.ruleset, self.state, event)
        self.event_log.append(event)
        self.state = next_state
        return next_state

    def _resolve_entity_token(self, token: str) -> str | None:
        cleaned = token.lstrip("@").strip().lower()
        if not cleaned:
            return None
        if cleaned in self.state.entities:
            return cleaned
        room_id = self._current_room().room_id
        in_room = [eid for eid, rm in self.entity_rooms.items() if rm == room_id]
        for eid in in_room + sorted(self.state.entities):
            ent = self.state.entities.get(eid)
            if ent is None:
                continue
            if cleaned in ent.name.lower() or cleaned in eid.lower():
                return eid
        return None

    def _render_room_lines(self, observer_id: str | None = None) -> tuple[str, ...]:
        obs = observer_id or self.active_entity_id
        room = self._current_room()
        exits_str = ", ".join(
            f"{direction} -> {self.rooms[dest].name}"
            for direction, dest in sorted(room.exits.items())
        )
        lines: list[str] = [
            f"== {room.name} [Z{room.floor_index}] ({room.room_id}) ==",
            room.description,
            f"Exits: {exits_str or 'none'}",
        ]
        if room.prop_notes:
            lines.append(f"Notable features: {', '.join(room.prop_notes)}")

        visible_occupants: list[str] = []
        for eid in sorted(self.state.entities):
            if self.entity_rooms.get(eid) != room.room_id:
                continue
            if eid == obs:
                continue
            if not is_target_visible_to_observer(self.ruleset, self.state, obs, eid):
                continue
            perceived = resolve_perceived_identity(self.ruleset, self.state, eid, observer_id=obs)
            marker = f" [disguised as {perceived.perceived_name}]" if perceived.is_disguised else ""
            visible_occupants.append(f"{perceived.perceived_name} ({eid}){marker}")
        lines.append(f"Present: {', '.join(visible_occupants) if visible_occupants else 'nobody'}")
        return tuple(lines)

    def _make_turn_result(
        self,
        *,
        raw: str,
        category: str,
        lines: Sequence[str],
        error: str | None = None,
    ) -> MudTurnResult:
        pending_skip = (
            self.state.pending_time_skip.model_dump(mode="json")
            if self.state.pending_time_skip is not None
            else None
        )
        return MudTurnResult(
            command_raw=raw,
            category=category,
            output_lines=tuple(lines),
            state_hash=state_hash(self.state),
            event_seq=self.state.event_seq,
            elapsed_world_seconds=self.state.elapsed_world_seconds,
            current_room_id=self._current_room().room_id,
            pending_manual_roll=dict(self.pending_manual_action)
            if self.pending_manual_action is not None
            else None,
            pending_time_skip=cast(dict[str, object] | None, pending_skip),
            error=error,
        )

    def _room_topology_edges(self) -> tuple[RoomTopologyEdge, ...]:
        edges: list[RoomTopologyEdge] = []
        for rm_id, rm in sorted(self.rooms.items()):
            for direction, dest_id in sorted(rm.exits.items()):
                dest_room = self.rooms.get(dest_id)
                is_shaft = dest_room is not None and dest_room.floor_index != rm.floor_index
                edges.append(
                    RoomTopologyEdge(
                        from_room_id=rm_id,
                        to_room_id=dest_id,
                        direction_label=direction,
                        from_room_name=rm.name,
                        is_vertical_shaft=is_shaft,
                    )
                )
        return tuple(edges)

    def _handle_movement(self, raw: str, verb: str, args: tuple[str, ...]) -> MudTurnResult:
        direction = (args[0].lower() if (verb == "go" and args) else verb.lower()).strip()
        direction = _DIR_ALIASES.get(direction, direction)
        room = self._current_room()
        dest_id = room.exits.get(direction)
        if dest_id is None:
            return self._make_turn_result(
                raw=raw,
                category="movement",
                lines=(f"No exit '{direction}' from {room.name}.",),
                error=f"Invalid direction '{direction}'.",
            )
        prev_floor = room.floor_index
        self.entity_rooms[self.active_entity_id] = dest_id
        new_room = self.rooms[dest_id]
        lines = list(self._render_room_lines())
        if new_room.floor_index != prev_floor:
            lines.insert(
                0,
                f"Floor transition: Z{prev_floor} -> Z{new_room.floor_index}.",
            )
        return self._make_turn_result(raw=raw, category="movement", lines=lines)

    def _handle_sheet(
        self,
        raw: str,
        args: tuple[str, ...],
        seat_id: str,
    ) -> MudTurnResult:
        if args and args[0].lower() == "set" and len(args) >= 4:
            sub = args[1].lower()
            key = args[2]
            val_str = args[3]
            reason = " ".join(args[4:]) if len(args) > 4 else "cli_sheet_override"
            if sub == "prop":
                next_state, evt = apply_sheet_override(
                    self.ruleset,
                    self.state,
                    entity_id=self.active_entity_id,
                    property_overrides={key: _parse_scalar(val_str)},
                    actor_seat_id=seat_id,
                    reason=reason,
                )
                self._append_events((evt,), next_state)
                return self._make_turn_result(
                    raw=raw,
                    category="meta",
                    lines=(f"SHEET_OVERRIDE applied: {key} = {val_str} ({reason}).",),
                )
            if sub == "pool":
                try:
                    pool_int = int(val_str)
                except ValueError:
                    return self._make_turn_result(
                        raw=raw,
                        category="meta",
                        lines=(f"Pool value must be an integer, got '{val_str}'.",),
                        error="Invalid pool value",
                    )
                next_state, evt = apply_sheet_override(
                    self.ruleset,
                    self.state,
                    entity_id=self.active_entity_id,
                    pool_overrides={key: pool_int},
                    actor_seat_id=seat_id,
                    reason=reason,
                )
                self._append_events((evt,), next_state)
                return self._make_turn_result(
                    raw=raw,
                    category="meta",
                    lines=(f"SHEET_OVERRIDE applied: pool {key} = {pool_int} ({reason}).",),
                )

        if args and args[0].lower() in {"cond", "condition"} and len(args) >= 3:
            op = args[1].lower()
            cid = args[2]
            if op == "add":
                dur: int | None = None
                if len(args) >= 4:
                    try:
                        dur = int(args[3])
                    except ValueError:
                        dur = None
                next_state, evt = apply_sheet_override(
                    self.ruleset,
                    self.state,
                    entity_id=self.active_entity_id,
                    add_conditions={cid: dur},
                    actor_seat_id=seat_id,
                    reason="cli_sheet_condition_add",
                )
                self._append_events((evt,), next_state)
                return self._make_turn_result(
                    raw=raw,
                    category="meta",
                    lines=(f"SHEET_OVERRIDE added condition '{cid}'.",),
                )
            if op in {"remove", "rm", "clear"}:
                next_state, evt = apply_sheet_override(
                    self.ruleset,
                    self.state,
                    entity_id=self.active_entity_id,
                    remove_conditions=(cid,),
                    actor_seat_id=seat_id,
                    reason="cli_sheet_condition_remove",
                )
                self._append_events((evt,), next_state)
                return self._make_turn_result(
                    raw=raw,
                    category="meta",
                    lines=(f"SHEET_OVERRIDE removed condition '{cid}'.",),
                )

        if args and args[0].lower() == "tag" and len(args) >= 3:
            op = args[1].lower()
            tag_val = args[2]
            if op == "add":
                next_state, evt = apply_sheet_override(
                    self.ruleset,
                    self.state,
                    entity_id=self.active_entity_id,
                    add_tags=(tag_val,),
                    actor_seat_id=seat_id,
                    reason="cli_sheet_tag_add",
                )
                self._append_events((evt,), next_state)
                return self._make_turn_result(
                    raw=raw,
                    category="meta",
                    lines=(f"SHEET_OVERRIDE added tag '{tag_val}'.",),
                )
            if op in {"remove", "rm"}:
                next_state, evt = apply_sheet_override(
                    self.ruleset,
                    self.state,
                    entity_id=self.active_entity_id,
                    remove_tags=(tag_val,),
                    actor_seat_id=seat_id,
                    reason="cli_sheet_tag_remove",
                )
                self._append_events((evt,), next_state)
                return self._make_turn_result(
                    raw=raw,
                    category="meta",
                    lines=(f"SHEET_OVERRIDE removed tag '{tag_val}'.",),
                )

        target_eid = (
            self._resolve_entity_token(args[0]) if args else self.active_entity_id
        ) or self.active_entity_id
        ent = self.state.entities[target_eid]
        view = compute_entity_view(self.ruleset, ent)
        props_fmt = ", ".join(f"{k}={v}" for k, v in sorted(view.properties.items())) or "none"
        pools_fmt = (
            ", ".join(
                f"{k}={v}/{view.pool_maxes.get(k, '?')}" for k, v in sorted(view.pools.items())
            )
            or "none"
        )
        conds_fmt = ", ".join(view.conditions) or "none"
        tags_fmt = ", ".join(view.tags) or "none"
        presets_fmt = ", ".join(sorted(ent.disguise_presets)) or "none"
        lines = [
            f"Sheet: {ent.name} ({ent.entity_id}) [ruleset={self.ruleset.manifest.package_id}]",
            f"Properties: {props_fmt}",
            f"Pools: {pools_fmt}",
            f"Conditions: {conds_fmt}",
            f"Tags: {tags_fmt}",
            f"Active form: {view.active_form_id or 'base'}",
            f"Active disguise: {view.active_disguise_alias or 'none'} "
            f"(presented={view.presented_name or ent.name})",
            f"Disguise presets: {presets_fmt}",
        ]
        return self._make_turn_result(raw=raw, category="meta", lines=lines)

    def _pick_action(self, requested: str) -> ActionBlock | None:
        if requested in self.ruleset.actions:
            return self.ruleset.actions[requested]
        for _aid, act in sorted(self.ruleset.actions.items()):
            if requested in {"attack", "strike"} and act.requires_target:
                return act
            if act.label.lower() == requested.lower():
                return act
        if requested in {"attack", "strike"} and self.ruleset.actions:
            first_key = sorted(self.ruleset.actions)[0]
            return self.ruleset.actions[first_key]
        return None

    def _run_vm_action(
        self,
        raw: str,
        action_token: str,
        args: tuple[str, ...],
        *,
        force_auto_roll: bool = False,
    ) -> MudTurnResult:
        act = self._pick_action(action_token)
        if act is None:
            avail = ", ".join(sorted(self.ruleset.actions)) or "none"
            return self._make_turn_result(
                raw=raw,
                category="vm_action",
                lines=(f"Unknown action '{action_token}'. Available actions: {avail}",),
                error=f"Unknown action '{action_token}'",
            )

        target_id: str | None = None
        if args:
            target_id = self._resolve_entity_token(args[0])
        if act.requires_target and target_id is None:
            room_id = self._current_room().room_id
            for eid in sorted(self.state.entities):
                if eid != self.active_entity_id and self.entity_rooms.get(eid) == room_id:
                    target_id = eid
                    break
            if target_id is None:
                target_id = _default_observer_for_room(
                    self.state, self._current_room(), self.entity_rooms, self.active_entity_id
                )

        use_manual = False if force_auto_roll else self.manual_roll_mode
        try:
            res = execute_action(
                self.ruleset,
                self.state,
                self.active_entity_id,
                act.action_id,
                target_id=target_id,
                manual_roll_mode=use_manual,
                bypass_reactions=True,
            )
        except (ValueError, KeyError, PermissionError) as exc:
            return self._make_turn_result(
                raw=raw,
                category="vm_action",
                lines=(f"Cannot execute '{act.action_id}': {exc}",),
                error=str(exc),
            )

        if res.status == "manual_roll_required":
            mech = self.ruleset.resolutions.get(act.resolution_id or "")
            formula_desc = mech.randomizer.formula if mech is not None else act.resolution_id
            mod_desc = mech.modifier_formula if mech is not None else "0"
            tgt_desc = mech.target_formula if mech is not None else "none"
            self.pending_manual_action = {
                "action_id": act.action_id,
                "target_id": target_id,
                "resolution_id": act.resolution_id,
                "formula": formula_desc or "dice",
                "modifier_formula": mod_desc,
                "target_formula": tgt_desc,
            }
            return self._make_turn_result(
                raw=raw,
                category="vm_action",
                lines=(
                    f"Manual roll required for '{act.label}' ({act.action_id}): "
                    f"roll {formula_desc} mod({mod_desc}) vs target({tgt_desc}).",
                    "Apply physical result via `sheet set ...` or run `manual-roll resolve`.",
                ),
            )

        self.pending_manual_action = None
        self._append_events(res.events, res.state)
        lines: list[str] = [f"Executed '{act.label}' ({act.action_id})"]
        if res.roll_result is not None:
            tier_txt = res.roll_result.tier_label or res.roll_result.tier_id or "resolved"
            lines.append(f"Roll: {res.roll_result.breakdown} -> {tier_txt}")
        if self.state.clocks:
            clocks_str = ", ".join(f"{k}={v}" for k, v in sorted(self.state.clocks.items()))
            lines.append(f"Clocks: {clocks_str}")
        return self._make_turn_result(raw=raw, category="vm_action", lines=lines)

    def _handle_manual_roll_cmd(self, raw: str, tokens: list[str]) -> MudTurnResult:
        sub = tokens[1].lower() if len(tokens) > 1 else "status"
        if sub in {"on", "enable", "true"}:
            self.manual_roll_mode = True
            return self._make_turn_result(
                raw=raw,
                category="meta",
                lines=("Manual-roll mode enabled: resolution actions pause for tabletop dice.",),
            )
        if sub in {"off", "disable", "false"}:
            self.manual_roll_mode = False
            self.pending_manual_action = None
            return self._make_turn_result(
                raw=raw,
                category="meta",
                lines=("Manual-roll mode disabled: deterministic VM RNG active.",),
            )
        if sub == "resolve":
            if self.pending_manual_action is None:
                return self._make_turn_result(
                    raw=raw,
                    category="meta",
                    lines=("No pending manual-roll action.",),
                )
            act_id = str(self.pending_manual_action["action_id"])
            tgt = self.pending_manual_action.get("target_id")
            args = (str(tgt),) if isinstance(tgt, str) and tgt else ()
            return self._run_vm_action(raw, act_id, args, force_auto_roll=True)
        if sub == "cancel":
            self.pending_manual_action = None
            return self._make_turn_result(
                raw=raw,
                category="meta",
                lines=("Cleared pending manual-roll prompt.",),
            )
        state_lbl = "ON" if self.manual_roll_mode else "OFF"
        return self._make_turn_result(
            raw=raw,
            category="meta",
            lines=(f"Manual-roll mode: {state_lbl}",),
        )

    def _handle_form_cmd(self, raw: str, tokens: list[str], seat_id: str) -> MudTurnResult:
        sub = tokens[1].lower() if len(tokens) > 1 else "list"
        if sub == "list":
            avail = list_available_forms(self.ruleset, self.state.entities[self.active_entity_id])
            if not avail and self.ruleset.forms:
                avail = tuple(self.ruleset.forms[k] for k in sorted(self.ruleset.forms))
            cur = self.state.entities[self.active_entity_id].active_form
            cur_id = cur.form_id if cur is not None else "base"
            names = ", ".join(f"{f.form_id} ({f.label})" for f in avail) or "none declared"
            return self._make_turn_result(
                raw=raw,
                category="vm_action",
                lines=(f"Active form: {cur_id}", f"Available forms: {names}"),
            )
        if sub == "shift" and len(tokens) >= 3:
            fid = tokens[2]
            try:
                res = shift_into_form(
                    self.ruleset,
                    self.state,
                    self.active_entity_id,
                    fid,
                    actor_seat_id=seat_id,
                )
            except (KeyError, ValueError, PermissionError) as exc:
                return self._make_turn_result(
                    raw=raw,
                    category="vm_action",
                    lines=(f"Form shift failed: {exc}",),
                    error=str(exc),
                )
            self._append_events(res.events, res.state)
            return self._make_turn_result(
                raw=raw,
                category="vm_action",
                lines=(f"Shifted into form '{fid}'.",),
            )
        if sub == "revert":
            try:
                res = revert_form(
                    self.ruleset,
                    self.state,
                    self.active_entity_id,
                    actor_seat_id=seat_id,
                )
            except (KeyError, PermissionError) as exc:
                return self._make_turn_result(
                    raw=raw,
                    category="vm_action",
                    lines=(f"Form revert failed: {exc}",),
                    error=str(exc),
                )
            self._append_events(res.events, res.state)
            return self._make_turn_result(
                raw=raw,
                category="vm_action",
                lines=(f"Reverted from form '{res.previous_form_id or 'none'}'.",),
            )
        return self._make_turn_result(
            raw=raw,
            category="vm_action",
            lines=("Usage: form list | form shift <form_id> | form revert",),
        )

    def _handle_covert(
        self,
        raw: str,
        verb: str,
        args: tuple[str, ...],
        seat_id: str,
    ) -> MudTurnResult:
        if verb == "hide":
            if not is_pillar_active(self.ruleset, "stealth"):
                return self._make_turn_result(
                    raw=raw,
                    category="covert",
                    lines=("Stealth pillar is dormant in the active ruleset.",),
                )
            obs_id = (
                self._resolve_entity_token(args[0]) if args else None
            ) or _default_observer_for_room(
                self.state, self._current_room(), self.entity_rooms, self.active_entity_id
            )
            if obs_id is None:
                return self._make_turn_result(
                    raw=raw,
                    category="covert",
                    lines=("No observers present to hide from.",),
                )
            res = set_awareness_level(
                self.ruleset,
                self.state,
                obs_id,
                self.active_entity_id,
                "unaware",
                actor_seat_id=seat_id,
                gm_approved=True,
            )
            self._append_events(res.events, res.state)
            return self._make_turn_result(
                raw=raw,
                category="covert",
                lines=(f"Stealth updated: {obs_id} awareness of you is '{res.awareness_level}'.",),
            )

        if verb == "sneak":
            if not is_pillar_active(self.ruleset, "stealth"):
                return self._make_turn_result(
                    raw=raw,
                    category="covert",
                    lines=("Stealth pillar is dormant in the active ruleset.",),
                )
            if args:
                move_res = self._handle_movement(raw, "go", (args[0],))
                if move_res.error:
                    return move_res
                lines = list(move_res.output_lines)
            else:
                lines = []
            obs_id = _default_observer_for_room(
                self.state, self._current_room(), self.entity_rooms, self.active_entity_id
            )
            if obs_id is not None:
                res = set_awareness_level(
                    self.ruleset,
                    self.state,
                    obs_id,
                    self.active_entity_id,
                    "unaware",
                    actor_seat_id=seat_id,
                    gm_approved=True,
                )
                self._append_events(res.events, res.state)
                lines.insert(
                    0,
                    f"Moved quietly ({obs_id} awareness={res.awareness_level}).",
                )
            return self._make_turn_result(raw=raw, category="covert", lines=lines or ["Sneaking."])

        if verb in {"steal", "plant"}:
            if not is_pillar_active(self.ruleset, "theft"):
                return self._make_turn_result(
                    raw=raw,
                    category="covert",
                    lines=("Theft pillar is dormant in the active ruleset.",),
                )
            cleaned = [a for a in args if a.lower() not in {"from", "on", "to"}]
            if len(cleaned) < 2:
                return self._make_turn_result(
                    raw=raw,
                    category="covert",
                    lines=(f"Usage: {verb} <item_id> <target_entity>",),
                    error="Missing arguments",
                )
            item_id = cleaned[0]
            target_eid = self._resolve_entity_token(cleaned[1])
            if target_eid is None:
                return self._make_turn_result(
                    raw=raw,
                    category="covert",
                    lines=(f"Unknown entity '{cleaned[1]}'.",),
                    error=f"Unknown entity '{cleaned[1]}'",
                )
            src = target_eid if verb == "steal" else self.active_entity_id
            dst = self.active_entity_id if verb == "steal" else target_eid
            prov = "stolen" if verb == "steal" else "planted"
            try:
                res = transfer_scene_item(
                    self.ruleset,
                    self.state,
                    src,
                    dst,
                    item_id,
                    provenance_state=prov,
                    actor_seat_id=seat_id,
                    gm_approved=True,
                )
            except (KeyError, ValueError, PermissionError) as exc:
                return self._make_turn_result(
                    raw=raw,
                    category="covert",
                    lines=(f"{verb.title()} failed: {exc}",),
                    error=str(exc),
                )
            self._append_events(res.events, res.state)
            return self._make_turn_result(
                raw=raw,
                category="covert",
                lines=(f"Transferred '{item_id}' ({prov}) {src} -> {dst}.",),
            )

        if verb == "disguise":
            if not is_pillar_active(self.ruleset, "disguise"):
                return self._make_turn_result(
                    raw=raw,
                    category="covert",
                    lines=("Disguise pillar is dormant in the active ruleset.",),
                )
            sub = args[0].lower() if args else "list"
            if sub == "list":
                presets = list_disguise_presets(self.state, self.active_entity_id)
                desc = ", ".join(f"{p.preset_id} ({p.presented_name})" for p in presets) or "none"
                return self._make_turn_result(
                    raw=raw,
                    category="covert",
                    lines=(f"Saved disguise slots: {desc}",),
                )
            if sub == "save" and len(args) >= 4:
                preset_id = args[1]
                alias_id = args[2]
                dur: int | None = None
                name_parts: list[str] = []
                idx = 3
                while idx < len(args):
                    if args[idx] == "--duration" and idx + 1 < len(args):
                        dur = int(args[idx + 1])
                        idx += 2
                        continue
                    name_parts.append(args[idx])
                    idx += 1
                presented_name = " ".join(name_parts) or alias_id
                preset = DisguisePreset(
                    preset_id=preset_id,
                    label=presented_name,
                    alias_id=alias_id,
                    presented_name=presented_name,
                    don_duration_seconds=dur,
                )
                res = save_disguise_preset(
                    self.ruleset,
                    self.state,
                    self.active_entity_id,
                    preset,
                    actor_seat_id=seat_id,
                )
                self._append_events(res.events, res.state)
                return self._make_turn_result(
                    raw=raw,
                    category="covert",
                    lines=(f"Saved disguise slot '{preset_id}' as '{presented_name}'.",),
                )
            if sub == "don" and len(args) >= 2:
                preset_id = args[1]
                now_flag = "--now" in args
                try:
                    res = don_disguise_preset(
                        self.ruleset,
                        self.state,
                        self.active_entity_id,
                        preset_id,
                        actor_seat_id=seat_id,
                        immediate=now_flag,
                        propose_time_skip=not now_flag,
                        required_voter_seat_ids=(seat_id,),
                        room_id=self._current_room().room_id,
                    )
                except (KeyError, ValueError, PermissionError) as exc:
                    return self._make_turn_result(
                        raw=raw,
                        category="covert",
                        lines=(f"Disguise don failed: {exc}",),
                        error=str(exc),
                    )
                self._append_events(res.events, res.state)
                if res.active_disguise is not None:
                    return self._make_turn_result(
                        raw=raw,
                        category="covert",
                        lines=(
                            f"Donned disguise '{preset_id}' "
                            f"(presented={res.active_disguise.presented_name}).",
                        ),
                    )
                return self._make_turn_result(
                    raw=raw,
                    category="covert",
                    lines=(
                        f"Started timed disguise prep for '{preset_id}' with time-skip proposal.",
                    ),
                )
            if sub == "apply" and len(args) >= 3:
                alias_id = args[1]
                presented = " ".join(args[2:])
                res = apply_disguise(
                    self.ruleset,
                    self.state,
                    self.active_entity_id,
                    alias_id,
                    presented,
                    actor_seat_id=seat_id,
                )
                self._append_events(res.events, res.state)
                return self._make_turn_result(
                    raw=raw,
                    category="covert",
                    lines=(f"Equipped disguise '{presented}' ({alias_id}).",),
                )
            if sub in {"remove", "blow", "clear", "off"}:
                res = blow_disguise(
                    self.ruleset,
                    self.state,
                    self.active_entity_id,
                    actor_seat_id=seat_id,
                )
                self._append_events(res.events, res.state)
                return self._make_turn_result(
                    raw=raw,
                    category="covert",
                    lines=("Cleared active disguise overlay.",),
                )
            return self._make_turn_result(
                raw=raw,
                category="covert",
                lines=(
                    "Usage: disguise list | save <slot> <alias> <name> [--duration <s>] "
                    "| don <slot> [--now] | apply <alias> <name> | remove",
                ),
            )

        return self._make_turn_result(
            raw=raw, category="covert", lines=("Unsupported covert cmd.",)
        )

    def _handle_time_control(
        self,
        raw: str,
        verb: str,
        args: tuple[str, ...],
        seat_id: str,
        seat_role: SeatRole,
    ) -> MudTurnResult:
        if verb == "wait":
            secs = 60
            if args:
                try:
                    secs = int(args[0])
                except ValueError:
                    return self._make_turn_result(
                        raw=raw,
                        category="time_control",
                        lines=(f"Expected integer seconds for wait, got '{args[0]}'.",),
                        error="Invalid wait seconds",
                    )
            res = advance_world_time(
                self.ruleset,
                self.state,
                secs,
                actor_seat_id=seat_id,
                reason="cli_wait",
            )
            self._append_events(res.events, res.state)
            completed_names = ", ".join(a.label for a in res.completed_activities)
            msg = f"World time +{secs}s (total {self.state.elapsed_world_seconds}s)."
            lines = [msg]
            if completed_names:
                lines.append(f"Completed timed activities: {completed_names}")
            return self._make_turn_result(raw=raw, category="time_control", lines=lines)

        sub = args[0].lower() if args else "status"
        try:
            if sub == "status":
                prop = self.state.pending_time_skip
                lines = [f"World clock: {self.state.elapsed_world_seconds}s"]
                if prop is not None:
                    lines.append(
                        f"Pending time skip '{prop.label}' ({prop.duration_seconds}s, "
                        f"status={prop.status}, votes={dict(prop.votes)})"
                    )
                else:
                    lines.append("Pending time skip: none")
                if self.state.active_timed_activities:
                    tasks = ", ".join(
                        f"{act.activity_id}({act.remaining_seconds}s:{act.status})"
                        for act in self.state.active_timed_activities.values()
                    )
                    lines.append(f"Active timed tasks: {tasks}")
                return self._make_turn_result(raw=raw, category="time_control", lines=lines)

            if sub == "propose" and len(args) >= 2:
                dur = int(args[1])
                lbl = " ".join(args[2:]) or f"Time skip ({dur}s)"
                res = propose_time_skip(
                    self.ruleset,
                    self.state,
                    self.active_entity_id,
                    lbl,
                    dur,
                    proposer_seat_id=seat_id,
                    required_voter_seat_ids=(seat_id,),
                    auto_commit_if_solo=False,
                )
                self._append_events(res.events, res.state)
                return self._make_turn_result(
                    raw=raw,
                    category="time_control",
                    lines=(f"Proposed time skip '{lbl}' ({dur}s). Vote with `timeskip vote`.",),
                )

            if sub == "vote" and len(args) >= 2:
                choice_raw = args[1].lower()
                if choice_raw not in {"approve", "hold_act_first", "keep_exploring"}:
                    raise ValueError("Vote must be approve, hold_act_first, or keep_exploring.")
                voter = args[2] if len(args) >= 3 else seat_id
                res = vote_on_time_skip(
                    self.ruleset,
                    self.state,
                    voter,
                    cast(TimeSkipVoteChoice, choice_raw),
                )
                self._append_events(res.events, res.state)
                return self._make_turn_result(
                    raw=raw,
                    category="time_control",
                    lines=(
                        f"Vote '{choice_raw}' recorded for '{voter}'. "
                        f"World clock={self.state.elapsed_world_seconds}s",
                    ),
                )

            if sub == "schedule" and len(args) >= 2:
                lbl = " ".join(args[1:])
                res = schedule_concurrent_activity(
                    self.ruleset,
                    self.state,
                    self.active_entity_id,
                    lbl,
                    actor_seat_id=seat_id,
                )
                self._append_events(res.events, res.state)
                return self._make_turn_result(
                    raw=raw,
                    category="time_control",
                    lines=(f"Scheduled concurrent activity: '{lbl}'.",),
                )

            if sub == "gm" and len(args) >= 2:
                dur = int(args[1])
                lbl = " ".join(args[2:]) or "GM Time Skip"
                res = gm_trigger_time_skip(
                    self.ruleset,
                    self.state,
                    dur,
                    label=lbl,
                    gm_seat_id=seat_id,
                    seat_role=seat_role,
                    proposer_entity_id=self.active_entity_id,
                )
                self._append_events(res.events, res.state)
                return self._make_turn_result(
                    raw=raw,
                    category="time_control",
                    lines=(
                        f"GM triggered time skip '{lbl}' (+{dur}s). "
                        f"World clock={self.state.elapsed_world_seconds}s",
                    ),
                )

            if sub == "interrupt" and len(args) >= 2:
                elapsed = int(args[1])
                reason = " ".join(args[2:]) or "interrupted"
                res = interrupt_time_skip(
                    self.ruleset,
                    self.state,
                    elapsed,
                    reason=reason,
                    actor_seat_id=seat_id,
                )
                self._append_events(res.events, res.state)
                return self._make_turn_result(
                    raw=raw,
                    category="time_control",
                    lines=(
                        f"Time skip interrupted after {elapsed}s ({reason}). "
                        f"World clock={self.state.elapsed_world_seconds}s",
                    ),
                )
        except (ValueError, PermissionError) as exc:
            return self._make_turn_result(
                raw=raw,
                category="time_control",
                lines=(f"Time-skip error: {exc}",),
                error=str(exc),
            )

        return self._make_turn_result(
            raw=raw,
            category="time_control",
            lines=(
                "Usage: timeskip status | propose <s> [lbl] | "
                "vote <approve|hold_act_first|keep_exploring> | schedule <lbl> | "
                "gm <s> | interrupt <elapsed_s> [reason]",
            ),
        )

    def _handle_flow_cmd(self, raw: str, tokens: list[str]) -> MudTurnResult:
        sub = tokens[1].lower() if len(tokens) > 1 else "status"
        if sub == "start":
            ctxs = {
                eid: compute_entity_view(self.ruleset, ent).to_eval_context()
                for eid, ent in sorted(self.state.entities.items())
            }
            rng = DeterministicRngStream(
                seed=f"{self.campaign.scene_seed}:init:{self.state.event_seq}",
                stream_name="initiative",
            )
            next_flow = start_round_initiative(self.ruleset, ctxs, rng)
        elif sub in {"next", "advance"}:
            next_flow = advance_turn(self.state.flow)
        elif sub == "delay":
            target = tokens[2] if len(tokens) >= 3 else self.active_entity_id
            next_flow = delay_turn(self.state.flow, target)
        elif tokens[0].lower() == "spotlight" and len(tokens) >= 2:
            participants = tuple(sorted(self.state.entities))
            next_flow = handoff_spotlight(self.state.flow, tokens[1], participants)
        else:
            f = self.state.flow
            return self._make_turn_result(
                raw=raw,
                category="meta",
                lines=(
                    f"Flow mode={f.mode}, round={f.round_number}, active={f.active_entity_id}, "
                    f"order={list(f.turn_order)}",
                ),
            )

        evt = VmEvent(
            event_id=self._next_event_id(),
            event_type="FLOW_UPDATED",
            actor_id=self.active_entity_id,
            payload={"flow": next_flow.model_dump(mode="json")},
        )
        next_state = self._apply_new_event(evt)
        _ = next_state
        f = self.state.flow
        return self._make_turn_result(
            raw=raw,
            category="meta",
            lines=(
                f"Flow updated: mode={f.mode}, round={f.round_number}, active={f.active_entity_id}",
            ),
        )

    def execute_command(
        self,
        raw_line: str,
        *,
        seat_id: str | None = None,
        seat_role: SeatRole | None = None,
    ) -> MudTurnResult:
        """Parse and deterministically execute one Terminal MUD command."""
        raw = raw_line.strip()
        eff_seat = seat_id or self.active_seat_id
        eff_role: SeatRole = seat_role or self.active_seat_role
        if not raw:
            return self._make_turn_result(
                raw=raw_line,
                category="meta",
                lines=("Type 'help' for commands or 'look' to inspect the room.",),
            )

        tokens = raw.split()
        cmd_word = tokens[0].lower().lstrip("/")
        if not cmd_word and len(tokens) == 1:
            return self._make_turn_result(
                raw=raw_line,
                category="meta",
                lines=("Type 'help' for commands or 'look' to inspect the room.",),
            )

        # Handle CLI-specific extension verbs directly before general MUD routing
        if cmd_word in {"manual-roll", "manual_roll"}:
            return self._handle_manual_roll_cmd(raw, tokens)
        if cmd_word == "form":
            return self._handle_form_cmd(raw, tokens, eff_seat)
        if cmd_word in {"turn", "spotlight"}:
            return self._handle_flow_cmd(raw, tokens)
        if cmd_word == "actions":
            acts = ", ".join(
                f"{aid} ({act.label})" for aid, act in sorted(self.ruleset.actions.items())
            )
            return self._make_turn_result(
                raw=raw,
                category="meta",
                lines=(f"Ruleset actions: {acts or 'none'}",),
            )
        if cmd_word == "clocks":
            clks = ", ".join(f"{k}={v}" for k, v in sorted(self.state.clocks.items())) or "none"
            return self._make_turn_result(
                raw=raw, category="meta", lines=(f"Scene clocks: {clks}",)
            )
        if cmd_word == "time":
            return self._handle_time_control(raw, "timeskip", ("status",), eff_seat, eff_role)

        parsed = parse_mud_command(
            raw,
            custom_verbs=tuple(sorted(self.ruleset.actions)),
        )

        if parsed.category == "movement":
            return self._handle_movement(raw, parsed.verb, parsed.args)

        if parsed.category == "observation":
            if parsed.verb in {"look", "l"} and not parsed.target_token:
                return self._make_turn_result(
                    raw=raw,
                    category="observation",
                    lines=self._render_room_lines(),
                )
            if parsed.verb in {"search"}:
                room = self._current_room()
                notices = len(self.state.pending_missing_notices)
                props_txt = ", ".join(room.prop_notes) or "no hidden latches"
                return self._make_turn_result(
                    raw=raw,
                    category="observation",
                    lines=(
                        f"Searched {room.name}: {props_txt}.",
                        f"Pending covert notices: {notices}.",
                    ),
                )
            tgt = self._resolve_entity_token(parsed.target_token or "")
            if tgt is None:
                return self._make_turn_result(
                    raw=raw,
                    category="observation",
                    lines=(f"You inspect '{parsed.target_token}' carefully.",),
                )
            perceived = resolve_perceived_identity(
                self.ruleset,
                self.state,
                tgt,
                observer_id=self.active_entity_id,
            )
            return self._make_turn_result(
                raw=raw,
                category="observation",
                lines=(
                    f"{perceived.perceived_name} ({tgt}) — tags={list(perceived.presented_tags)}",
                ),
            )

        if parsed.category == "inventory":
            inv = self.state.entity_inventories.get(self.active_entity_id)
            if inv is None or not inv.items:
                return self._make_turn_result(
                    raw=raw,
                    category="inventory",
                    lines=("Inventory is empty.",),
                )
            item_lines = [
                f"- {item.name} ({item.item_id}) [prov={item.provenance_state}, "
                f"access={item.slot_accessibility}]"
                for item in sorted(inv.items.values(), key=lambda it: it.item_id)
            ]
            return self._make_turn_result(raw=raw, category="inventory", lines=item_lines)

        if parsed.category == "covert":
            return self._handle_covert(raw, parsed.verb, parsed.args, eff_seat)

        if parsed.category == "time_control":
            return self._handle_time_control(raw, parsed.verb, parsed.args, eff_seat, eff_role)

        if parsed.category == "vm_action" or parsed.category == "custom_command":
            action_tok = parsed.args[0] if parsed.verb == "use" and parsed.args else parsed.verb
            rem_args = parsed.args[1:] if (parsed.verb == "use" and parsed.args) else parsed.args
            return self._run_vm_action(raw, action_tok, rem_args)

        if parsed.category == "roll":
            self._manual_roll_counter += 1
            rng = DeterministicRngStream(
                seed=f"{self.campaign.scene_seed}:cli_roll:{self._manual_roll_counter}",
                stream_name="cli_dice",
            )
            if parsed.verb == "flip":
                cnt = parsed.args[0] if parsed.args else "1"
                spec = RandomizerSpec(kind="coin_flip", pool_size_formula=cnt)
            else:
                formula = parsed.args[0] if parsed.args else "1d6"
                spec = RandomizerSpec(kind="dice_formula", formula=formula)
            try:
                roll_res, _ = resolve_randomizer(spec, rng, {})
            except ValueError as exc:
                return self._make_turn_result(
                    raw=raw,
                    category="roll",
                    lines=(f"Roll error: {exc}",),
                    error=str(exc),
                )
            return self._make_turn_result(
                raw=raw,
                category="roll",
                lines=(f"Rolled: {roll_res.breakdown}",),
            )

        if parsed.category == "meta":
            if parsed.verb in {"help", "?"}:
                return self._make_turn_result(
                    raw=raw,
                    category="meta",
                    lines=(
                        "Commands: look, n/s/e/w/u/d, actions, use <action> [target], "
                        "sheet [set prop|pool <id> <val>], manual-roll on|off|resolve, "
                        "form list|shift <id>|revert, hide|sneak|steal|plant|disguise, "
                        "timeskip|wait, inv, roll <expr>, say|whisper|shout|act, quit",
                    ),
                )
            if parsed.verb == "sheet":
                return self._handle_sheet(raw, parsed.args, eff_seat)
            if parsed.verb in {"status", "who"}:
                ent = self.state.entities[self.active_entity_id]
                rm = self._current_room()
                return self._make_turn_result(
                    raw=raw,
                    category="meta",
                    lines=(
                        f"Campaign={self.campaign.campaign_id} "
                        f"Ruleset={self.ruleset.manifest.package_id} "
                        f"Room={rm.room_id} [Z{rm.floor_index}] "
                        f"WorldTime={self.state.elapsed_world_seconds}s Seq={self.state.event_seq} "
                        f"Actor={ent.name}",
                    ),
                )
            return self._make_turn_result(
                raw=raw,
                category="meta",
                lines=(f"{parsed.verb}: active in Phase 2.5 preview.",),
            )

        if parsed.category == "communication":
            actor = self.state.entities[self.active_entity_id]
            clean = parsed.speech.clean_text if parsed.speech is not None else raw
            if parsed.verb == "shout":
                res = resolve_shout_propagation(
                    actor.name,
                    clean,
                    self._current_room().room_id,
                    self._room_topology_edges(),
                )
                lines = [res.room_text]
                for rm_id, bleed in sorted(res.adjacent_bleed.items()):
                    lines.append(f"[{rm_id}] {bleed}")
                return self._make_turn_result(raw=raw, category="communication", lines=lines)
            if parsed.verb == "whisper":
                target_id = (
                    self._resolve_entity_token(parsed.target_token or "")
                    or _default_observer_for_room(
                        self.state, self._current_room(), self.entity_rooms, self.active_entity_id
                    )
                    or self.active_entity_id
                )
                tgt_name = self.state.entities[target_id].name
                deliveries = resolve_whisper_eavesdrop(
                    self.active_entity_id,
                    actor.name,
                    target_id,
                    tgt_name,
                    clean,
                    listeners=(),
                )
                return self._make_turn_result(
                    raw=raw,
                    category="communication",
                    lines=tuple(d.rendered_text for d in deliveries[:1])
                    or (f"{actor.name} whispers quietly to {tgt_name}.",),
                )
            return self._make_turn_result(
                raw=raw,
                category="communication",
                lines=(f'{actor.name} ({parsed.verb}): "{clean}"',),
            )

        if parsed.category == "emote":
            actor = self.state.entities[self.active_entity_id]
            beats = parsed.pose_beats
            if not beats:
                beats, _, _ = parse_mixed_pose(raw)
            rendered = render_mixed_pose(
                self.active_entity_id,
                actor.name,
                beats,
                entity_names={eid: e.name for eid, e in self.state.entities.items()},
            )
            return self._make_turn_result(raw=raw, category="emote", lines=(rendered.to_room,))

        if parsed.category == "social_emote" and parsed.verb in BUILTIN_EMOTES:
            actor = self.state.entities[self.active_entity_id]
            spec = BUILTIN_EMOTES[parsed.verb]
            tgt_id = (
                self._resolve_entity_token(parsed.target_token or "")
                if parsed.target_token
                else None
            )
            tgt_name = self.state.entities[tgt_id].name if tgt_id is not None else None
            perspectives = render_emote(
                spec,
                actor.name,
                target_name=tgt_name,
                adverb=parsed.adverb,
                speech=parsed.speech.clean_text if parsed.speech is not None else None,
            )
            return self._make_turn_result(
                raw=raw,
                category="social_emote",
                lines=(perspectives.to_room,),
            )

        # Fallback: record non-mutating narrative action cleanly (Zero-AI mode)
        return self._make_turn_result(
            raw=raw,
            category="narrative_fallback",
            lines=(
                f"[Deterministic Director] Noted narrative input: '{raw}'. "
                "Use 'actions' or 'help' for ruleset actions.",
            ),
        )

    def create_checkpoint(self, label: str = "manual") -> CheckpointSummary:
        """Record an immutable replayable checkpoint at the current event_seq."""
        cp = CheckpointSummary(
            checkpoint_id=f"cp_{len(self.checkpoints) + 1:04d}",
            campaign_id=self.campaign.campaign_id,
            event_seq=self.state.event_seq,
            state_hash=state_hash(self.state),
            label=label,
        )
        self.checkpoints.append(cp)
        return cp

    def rewind_to_event(self, target_event_seq: int) -> CheckpointSummary:
        """Rewind authoritative state cleanly by replaying initial_state[:target_event_seq]."""
        if target_event_seq < 0 or target_event_seq > len(self.event_log):
            raise ValueError(
                f"target_event_seq must be in [0, {len(self.event_log)}], got {target_event_seq}."
            )
        kept = self.event_log[:target_event_seq]
        rewound_state = replay_events(self.ruleset, self.initial_state, kept)
        self.event_log = kept
        self.state = rewound_state
        self.pending_manual_action = None
        return self.create_checkpoint(label=f"rewind_seq_{target_event_seq}")

    def verify_replay_hash(self) -> bool:
        """Verify event-log replay hash equals live SceneState hash."""
        replayed = replay_events(self.ruleset, self.initial_state, self.event_log)
        return state_hash(replayed) == state_hash(self.state)

    def to_snapshot_dict(self) -> dict[str, object]:
        """Serialize complete session state & event log to JSON-compatible dict."""
        return {
            "campaign": self.campaign.model_dump(mode="json"),
            "initial_state": self.initial_state.model_dump(mode="json"),
            "state": self.state.model_dump(mode="json"),
            "event_log": [e.model_dump(mode="json") for e in self.event_log],
            "entity_rooms": dict(self.entity_rooms),
            "checkpoints": [cp.model_dump(mode="json") for cp in self.checkpoints],
            "active_entity_id": self.active_entity_id,
            "active_seat_id": self.active_seat_id,
            "active_seat_role": self.active_seat_role,
            "manual_roll_mode": self.manual_roll_mode,
        }

    @classmethod
    def from_snapshot_dict(
        cls,
        payload: Mapping[str, object],
        ruleset: RulesetSchema,
    ) -> MudSessionEngine:
        """Restore a MudSessionEngine from a persisted JSON snapshot."""
        campaign = CampaignMetadata.model_validate(payload["campaign"])
        initial_state = SceneState.model_validate(payload["initial_state"])
        state = SceneState.model_validate(payload["state"])
        raw_events = cast(Sequence[object], payload.get("event_log", ()))
        events = [VmEvent.model_validate(e) for e in raw_events]
        raw_rooms = cast(Mapping[str, object], payload.get("entity_rooms", {}))
        entity_rooms = {str(k): str(v) for k, v in raw_rooms.items()}
        raw_cps = cast(Sequence[object], payload.get("checkpoints", ()))
        checkpoints = [CheckpointSummary.model_validate(c) for c in raw_cps]
        return cls(
            campaign,
            ruleset,
            initial_state=initial_state,
            state=state,
            event_log=events,
            entity_rooms=entity_rooms,
            checkpoints=checkpoints,
            active_entity_id=str(payload.get("active_entity_id", "pc_lead")),
            active_seat_id=str(payload.get("active_seat_id", "seat_host")),
            active_seat_role=cast(SeatRole, payload.get("active_seat_role", "gm")),
            manual_roll_mode=bool(payload.get("manual_roll_mode", False)),
        )
