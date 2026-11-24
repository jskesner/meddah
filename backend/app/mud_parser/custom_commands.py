"""Host-created custom emotes, 4-step declarative ECA commands, RBAC & aliases."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Mapping, Sequence
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from app.mud_parser.social_dsl import parse_mud_command
from app.mud_parser.social_emote_library import (
    EmoteSpec,
    SemanticValence,
    list_emote_completions,
)

CommandScope = Literal[
    "room_or_poi_only",
    "region_or_hub_only",
    "campaign_overlay",
    "guild_server_global",
    "package_bundled",
]
CommandEligibility = Literal[
    "all_players",
    "requires_tag_or_faction",
    "gm_only",
    "host_admin_only",
]
CommandResolutionKind = Literal[
    "unconditional",
    "skill_check",
    "contested_check",
    "target_confirmation",
    "random_table",
]
CommandPayloadKind = Literal[
    "mud_text",
    "audio_cue",
    "vfx_cue",
    "modify_pool",
    "set_property",
    "add_condition",
    "remove_condition",
    "add_item",
    "remove_item",
    "trigger_contraption",
    "advance_clock",
    "teleport",
    "open_handout",
    "open_ui_drawer",
    "advance_quest",
    "record_deed",
]
OutcomeBranch = Literal["success", "partial", "failure"]


class CustomEmoteBlock(BaseModel):
    """Host/GM-authored custom 3-perspective parameterized social emote."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    emote_id: str = Field(min_length=1)
    verb: str = Field(min_length=1)
    aliases: tuple[str, ...] = ()
    no_target_actor: str = Field(min_length=1)
    no_target_room: str = Field(min_length=1)
    targeted_actor: str = Field(min_length=1)
    targeted_target: str = Field(min_length=1)
    targeted_room: str = Field(min_length=1)
    valence: SemanticValence = "neutral"
    requires: str = "true"
    audio_clip_ref: str | None = None
    vfx_cue: str | None = None
    scope: CommandScope = "campaign_overlay"
    scope_target_id: str | None = None
    eligibility: CommandEligibility = "all_players"
    required_tags: tuple[str, ...] = ()

    def to_emote_spec(self) -> EmoteSpec:
        """Convert into runtime EmoteSpec consumed by the social emote renderer."""
        return EmoteSpec(
            verb=self.verb.lower(),
            aliases=tuple(a.lower() for a in self.aliases),
            category="custom",
            valence=self.valence,
            no_target_actor=self.no_target_actor,
            no_target_room=self.no_target_room,
            targeted_actor=self.targeted_actor,
            targeted_target=self.targeted_target,
            targeted_room=self.targeted_room,
            requires=self.requires,
            audio_clip_ref=self.audio_clip_ref,
            vfx_cue=self.vfx_cue,
        )


class CommandCostSpec(BaseModel):
    """Resource pool or currency deduction checked in ECA Step 1."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    pool_id: str = Field(min_length=1)
    amount: int = Field(ge=1)


class RandomTableOutcome(BaseModel):
    """Inclusive roll range mapping for random_table ECA resolutions."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    min_roll: int
    max_roll: int
    branch: OutcomeBranch = "success"
    label: str = ""


class CommandResolutionStep(BaseModel):
    """ECA Step 2 optional skill check, target prompt, or random table lookup."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: CommandResolutionKind = "unconditional"
    resolution_id: str | None = None
    confirmation_prompt: str | None = None
    table_die_sides: int = Field(default=100, ge=2, le=1000)
    table_outcomes: tuple[RandomTableOutcome, ...] = ()


class CommandPayload(BaseModel):
    """Single deterministic state, UI, room, or narrative effect in ECA Step 3."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: CommandPayloadKind
    target_scope: Literal["actor", "target", "room", "table"] = "room"
    target_key: str = ""
    value: int | float | str | bool | None = None
    actor_text: str | None = None
    target_text: str | None = None
    room_text: str | None = None


class ChannelingSpec(BaseModel):
    """ECA Step 4 non-blocking interruptible channeling countdown gate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    channel_condition_id: str = Field(default="channeling", min_length=1)
    duration_turns: int = Field(default=1, ge=1)
    interrupt_on_move: bool = True
    interrupt_on_damage: bool = True
    completion_effects: tuple[CommandPayload, ...] = ()


class CommandActionPipeline(BaseModel):
    """4-step sandboxed declarative ECA pipeline (zero arbitrary code execution)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    requires: str = "true"
    failure_notice: str = "Requirements not met for this command."
    costs: tuple[CommandCostSpec, ...] = ()
    resolution_step: CommandResolutionStep = Field(default_factory=CommandResolutionStep)
    on_success: tuple[CommandPayload, ...] = ()
    on_partial: tuple[CommandPayload, ...] = ()
    on_failure: tuple[CommandPayload, ...] = ()
    channeling: ChannelingSpec | None = None


class CustomMudCommandBlock(BaseModel):
    """Host/GM-created custom MUD command backed by a declarative ECA pipeline."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    command_id: str = Field(min_length=1)
    verb: str = Field(min_length=1)
    aliases: tuple[str, ...] = ()
    description: str = ""
    syntax_hint: str = ""
    requires_target: bool = False
    scope: CommandScope = "campaign_overlay"
    scope_target_id: str | None = None
    eligibility: CommandEligibility = "all_players"
    required_tags: tuple[str, ...] = ()
    pipeline: CommandActionPipeline


class CommandAuthorRole(BaseModel):
    """RBAC author privileges checked when defining or modifying custom commands."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    seat_id: str = Field(min_length=1)
    is_host: bool = False
    is_gm: bool = False
    can_manage_custom_commands: bool = False


class CommandActorContext(BaseModel):
    """Lightweight actor and location context evaluated by the ECA pipeline."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    actor_id: str = Field(min_length=1)
    actor_name: str = Field(min_length=1)
    is_host: bool = False
    is_gm: bool = False
    room_id: str = ""
    region_id: str = ""
    in_combat: bool = False
    tags: tuple[str, ...] = ()
    conditions: tuple[str, ...] = ()
    room_tags: tuple[str, ...] = ()
    pools: dict[str, int] = Field(default_factory=dict)
    properties: dict[str, int | float | bool | str] = Field(default_factory=dict)


class EmittedCommandEffect(BaseModel):
    """Interpolated deterministic effect record emitted by a custom command."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: CommandPayloadKind
    target_scope: Literal["actor", "target", "room", "table"]
    target_key: str
    value: int | float | str | bool | None = None
    actor_text: str | None = None
    target_text: str | None = None
    room_text: str | None = None


class PendingConfirmationPrompt(BaseModel):
    """Interactive target consent request for duel/trade/ritual custom commands."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    command_id: str
    actor_id: str
    target_id: str
    prompt_text: str


class ChannelingTaskSpec(BaseModel):
    """Stateful turn-countdown task created when an ECA pipeline uses Step 4 channeling."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    command_id: str
    actor_id: str
    target_id: str | None = None
    target_name: str | None = None
    channel_condition_id: str
    remaining_turns: int
    interrupt_on_move: bool
    interrupt_on_damage: bool
    completion_effects: tuple[EmittedCommandEffect, ...] = ()


class CustomCommandExecutionResult(BaseModel):
    """Full deterministic execution output of a 4-step ECA custom command."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal[
        "executed",
        "blocked",
        "pending_confirmation",
        "channeling_started",
        "declined",
    ]
    command_id: str
    branch: Literal["success", "partial", "failure", "none"] = "none"
    blocked_reason: str | None = None
    costs_deducted: dict[str, int] = Field(default_factory=dict)
    table_roll: int | None = None
    effects: tuple[EmittedCommandEffect, ...] = ()
    pending_confirmation: PendingConfirmationPrompt | None = None
    channeling_task: ChannelingTaskSpec | None = None


class ClientCommandAliases(BaseModel):
    """Per-player personal shorthand alias definitions (`> alias eb = cast ...`)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    aliases: dict[str, str] = Field(default_factory=dict)

    def define_alias(self, name: str, template: str) -> ClientCommandAliases:
        """Register or overwrite a shorthand macro."""
        clean_name = name.strip().lstrip("/").lower()
        clean_tpl = template.strip()
        if not clean_name or not clean_tpl:
            raise ValueError("Alias name and expansion template must be non-empty.")
        updated = dict(self.aliases)
        updated[clean_name] = clean_tpl
        return ClientCommandAliases(aliases=updated)

    def remove_alias(self, name: str) -> ClientCommandAliases:
        """Delete an existing shorthand macro if present."""
        clean_name = name.strip().lstrip("/").lower()
        updated = dict(self.aliases)
        updated.pop(clean_name, None)
        return ClientCommandAliases(aliases=updated)

    def expand(self, raw_input: str) -> str:
        """Expand matching client alias and positional placeholders (@1/@*/$1/$*)."""
        parsed = parse_mud_command(raw_input, client_aliases=self.aliases)
        if "alias_expanded" not in parsed.flags:
            return raw_input
        # Re-run deterministic substitution so callers get exact expanded command string
        cur = raw_input.strip()
        for _ in range(4):
            parts = cur.split(None, 1)
            if not parts:
                break
            head = parts[0].lstrip("/").lower()
            if head in {"alias", "unalias", "aliases"} or head not in self.aliases:
                break
            tpl = self.aliases[head]
            tail = parts[1] if len(parts) > 1 else ""
            tokens = tail.split() if tail else []
            out = tpl
            used_pos = False
            for idx in range(1, 10):
                val = tokens[idx - 1] if idx - 1 < len(tokens) else ""
                for mark in (f"@{idx}", f"${idx}"):
                    if mark in out:
                        out = out.replace(mark, val)
                        used_pos = True
            for wild in ("@*", "$*"):
                if wild in out:
                    out = out.replace(wild, tail)
                    used_pos = True
            if not used_pos and tail:
                out = f"{out} {tail}"
            cur = re.sub(r"\s{2,}", " ", out).strip()
        return cur


def _lookup_path(ctx: Mapping[str, object], raw_path: str) -> object:
    cur: object = ctx
    for seg in raw_path.split("."):
        if isinstance(cur, Mapping):
            cur_map = cast(Mapping[object, object], cur)
            if seg in cur_map:
                cur = cur_map[seg]
                continue
        return None
    return cur


def _parse_literal_or_path(token: str, ctx: Mapping[str, object]) -> object:
    t = token.strip()
    if t.lower() == "true":
        return True
    if t.lower() == "false":
        return False
    if t.lower() in {"none", "null"}:
        return None
    if len(t) >= 2 and ((t[0] == "'" and t[-1] == "'") or (t[0] == '"' and t[-1] == '"')):
        return t[1:-1]
    if re.fullmatch(r"-?\d+", t):
        return int(t)
    if re.fullmatch(r"-?\d+\.\d+", t):
        return float(t)
    if t.startswith("@"):
        return _lookup_path(ctx, t)
    return _lookup_path(ctx, t)


def _eval_atomic_predicate(expr: str, ctx: Mapping[str, object]) -> bool:
    s = expr.strip()
    if not s:
        return True
    if s.startswith("!"):
        return not _eval_atomic_predicate(s[1:], ctx)
    if s.lower() == "true":
        return True
    if s.lower() == "false":
        return False

    m_call = re.fullmatch(r"(has_tag|has_condition)\(\s*([^,]+)\s*,\s*([^)]+)\s*\)", s)
    if m_call is not None:
        fn_name = m_call.group(1)
        container = _parse_literal_or_path(m_call.group(2), ctx)
        needle = str(_parse_literal_or_path(m_call.group(3), ctx) or "")
        if isinstance(container, Mapping):
            field = "tags" if fn_name == "has_tag" else "conditions"
            container_map = cast(Mapping[str, object], container)
            items: object = container_map.get(field, ())
        else:
            items = container
        if isinstance(items, Sequence) and not isinstance(items, str):
            seq_items = cast(Sequence[object], items)
            return needle in seq_items
        return False

    for op in (">=", "<=", "==", "!=", ">", "<"):
        if op in s:
            lhs_s, rhs_s = s.split(op, 1)
            lhs = _parse_literal_or_path(lhs_s, ctx)
            rhs = _parse_literal_or_path(rhs_s, ctx)
            if op == "==":
                return lhs == rhs
            if op == "!=":
                return lhs != rhs
            if isinstance(lhs, (int, float)) and isinstance(rhs, (int, float)):
                if op == ">=":
                    return lhs >= rhs
                if op == "<=":
                    return lhs <= rhs
                if op == ">":
                    return lhs > rhs
                return lhs < rhs
            return False

    val = _parse_literal_or_path(s, ctx)
    return bool(val)


def _default_eval_predicate(expr: str, ctx: Mapping[str, object]) -> bool:
    """Safe zero-eval boolean predicate evaluator when no VM callback is passed."""
    for or_part in expr.split("||"):
        and_ok = True
        for and_part in or_part.split("&&"):
            if not _eval_atomic_predicate(and_part, ctx):
                and_ok = False
                break
        if and_ok:
            return True
    return False


def _is_visible(
    scope: CommandScope,
    scope_target_id: str | None,
    eligibility: CommandEligibility,
    required_tags: tuple[str, ...],
    actor: CommandActorContext,
) -> bool:
    if scope == "room_or_poi_only" and scope_target_id and scope_target_id != actor.room_id:
        return False
    if scope == "region_or_hub_only" and scope_target_id and scope_target_id != actor.region_id:
        return False

    if eligibility == "host_admin_only":
        return actor.is_host
    if eligibility == "gm_only":
        return actor.is_gm or actor.is_host
    if eligibility == "requires_tag_or_faction":
        return not required_tags or bool(set(required_tags) & set(actor.tags))
    return True


def _format_effect(
    payload: CommandPayload,
    *,
    actor_name: str,
    target_name: str | None,
) -> EmittedCommandEffect:
    tgt = target_name or "someone"

    def _sub(text: str | None) -> str | None:
        if text is None:
            return None
        return text.replace("{actor}", actor_name).replace("{target}", tgt)

    return EmittedCommandEffect(
        kind=payload.kind,
        target_scope=payload.target_scope,
        target_key=payload.target_key,
        value=payload.value,
        actor_text=_sub(payload.actor_text),
        target_text=_sub(payload.target_text),
        room_text=_sub(payload.room_text),
    )


class CustomCommandRegistry(BaseModel):
    """Authoritative registry for Host/GM-authored custom MUD commands & emotes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    commands: dict[str, CustomMudCommandBlock] = Field(default_factory=dict)
    emotes: dict[str, CustomEmoteBlock] = Field(default_factory=dict)

    def _assert_can_author(self, author: CommandAuthorRole) -> None:
        if not (author.is_host or author.can_manage_custom_commands):
            raise PermissionError(
                f"Seat '{author.seat_id}' lacks Host or can_manage_custom_commands permission."
            )

    def register_command(
        self,
        author: CommandAuthorRole,
        command: CustomMudCommandBlock,
    ) -> CustomCommandRegistry:
        """Register or update a custom MUD command after RBAC verification."""
        self._assert_can_author(author)
        updated = dict(self.commands)
        updated[command.verb.lower()] = command
        return CustomCommandRegistry(commands=updated, emotes=dict(self.emotes))

    def register_emote(
        self,
        author: CommandAuthorRole,
        emote: CustomEmoteBlock,
    ) -> CustomCommandRegistry:
        """Register or update a custom 3-perspective social emote after RBAC verification."""
        self._assert_can_author(author)
        updated = dict(self.emotes)
        updated[emote.verb.lower()] = emote
        return CustomCommandRegistry(commands=dict(self.commands), emotes=updated)

    def resolve_command(self, verb: str) -> CustomMudCommandBlock | None:
        """Find a registered custom command by canonical verb or alias."""
        key = verb.strip().lower()
        if not key:
            return None
        if key in self.commands:
            return self.commands[key]
        for cmd in self.commands.values():
            if cmd.verb.lower() == key or key in {a.lower() for a in cmd.aliases}:
                return cmd
        return None

    def visible_commands_for(
        self,
        actor: CommandActorContext,
    ) -> tuple[CustomMudCommandBlock, ...]:
        """Return all custom commands active in actor's scope and eligibility tier."""
        visible = [
            cmd
            for cmd in self.commands.values()
            if _is_visible(
                cmd.scope,
                cmd.scope_target_id,
                cmd.eligibility,
                cmd.required_tags,
                actor,
            )
        ]
        visible.sort(key=lambda c: c.verb.lower())
        return tuple(visible)

    def visible_emotes_for(self, actor: CommandActorContext) -> tuple[CustomEmoteBlock, ...]:
        """Return all custom emotes active in actor's scope and eligibility tier."""
        visible = [
            em
            for em in self.emotes.values()
            if _is_visible(
                em.scope,
                em.scope_target_id,
                em.eligibility,
                em.required_tags,
                actor,
            )
        ]
        visible.sort(key=lambda e: e.verb.lower())
        return tuple(visible)

    def autocomplete_entries_for(
        self,
        actor: CommandActorContext,
        prefix: str = "",
    ) -> tuple[str, ...]:
        """Return live sorted `/command` & `/emote` palette completions for actor."""
        clean_prefix = prefix.strip().lower().lstrip("/:")
        visible_custom_emotes = {
            em.verb.lower(): em.to_emote_spec() for em in self.visible_emotes_for(actor)
        }
        entries: set[str] = set(list_emote_completions(clean_prefix, visible_custom_emotes))
        for cmd in self.visible_commands_for(actor):
            v = cmd.verb.lower()
            if v.startswith(clean_prefix):
                entries.add(v)
        return tuple(sorted(entries))


def execute_custom_command(
    registry: CustomCommandRegistry,
    verb: str,
    actor: CommandActorContext,
    *,
    target_id: str | None = None,
    target_name: str | None = None,
    eval_predicate: Callable[[str, dict[str, object]], object] | None = None,
    skill_check_resolver: Callable[
        [CustomMudCommandBlock, CommandActorContext, str | None],
        OutcomeBranch,
    ]
    | None = None,
    table_roll_fn: Callable[[CustomMudCommandBlock, int], int] | None = None,
    target_accepted: bool | None = None,
) -> CustomCommandExecutionResult:
    """Execute a Host-created custom MUD command through its 4-step sandboxed ECA pipeline."""
    cmd = registry.resolve_command(verb)
    if cmd is None:
        return CustomCommandExecutionResult(
            status="blocked",
            command_id=verb,
            blocked_reason=f"Unknown custom command '{verb}'.",
        )

    if not _is_visible(
        cmd.scope,
        cmd.scope_target_id,
        cmd.eligibility,
        cmd.required_tags,
        actor,
    ):
        return CustomCommandExecutionResult(
            status="blocked",
            command_id=cmd.command_id,
            blocked_reason="Command is not available in this scope or role.",
        )

    if cmd.requires_target and not target_id:
        return CustomCommandExecutionResult(
            status="blocked",
            command_id=cmd.command_id,
            blocked_reason=f"Command '{cmd.verb}' requires a @target.",
        )

    pipeline = cmd.pipeline

    # Step 1a: Precondition AST check
    self_ctx: dict[str, object] = {
        "entity_id": actor.actor_id,
        "name": actor.actor_name,
        "in_combat": actor.in_combat,
        "is_host": actor.is_host,
        "is_gm": actor.is_gm,
        "tags": list(actor.tags),
        "conditions": list(actor.conditions),
        "pools": dict(actor.pools),
        **actor.properties,
        **actor.pools,
    }
    eval_ctx: dict[str, object] = {
        "@self": self_ctx,
        "@room": {
            "room_id": actor.room_id,
            "region_id": actor.region_id,
            "tags": list(actor.room_tags),
        },
        "@target": (
            {"entity_id": target_id, "name": target_name or target_id}
            if target_id is not None
            else None
        ),
    }

    if eval_predicate is not None:
        gate_ok = bool(eval_predicate(pipeline.requires, eval_ctx))
    else:
        gate_ok = _default_eval_predicate(pipeline.requires, eval_ctx)

    if not gate_ok:
        return CustomCommandExecutionResult(
            status="blocked",
            command_id=cmd.command_id,
            blocked_reason=pipeline.failure_notice,
        )

    # Step 1b: Pool & currency cost verification
    costs_deducted: dict[str, int] = {}
    for cost in pipeline.costs:
        available = actor.pools.get(cost.pool_id, 0)
        if available < cost.amount:
            return CustomCommandExecutionResult(
                status="blocked",
                command_id=cmd.command_id,
                blocked_reason=(f"Insufficient {cost.pool_id} ({available} < {cost.amount})."),
            )
        costs_deducted[cost.pool_id] = costs_deducted.get(cost.pool_id, 0) + cost.amount

    # Step 2: Resolution step
    step = pipeline.resolution_step
    branch: OutcomeBranch = "success"
    table_roll: int | None = None

    if step.kind == "target_confirmation":
        tgt_id = target_id or ""
        if target_accepted is None:
            prompt_tpl = (
                step.confirmation_prompt
                or "{actor} challenges or invites {target} via '{verb}'. Accept?"
            )
            prompt_text = (
                prompt_tpl.replace("{actor}", actor.actor_name)
                .replace("{target}", target_name or tgt_id)
                .replace("{verb}", cmd.verb)
            )
            return CustomCommandExecutionResult(
                status="pending_confirmation",
                command_id=cmd.command_id,
                pending_confirmation=PendingConfirmationPrompt(
                    command_id=cmd.command_id,
                    actor_id=actor.actor_id,
                    target_id=tgt_id,
                    prompt_text=prompt_text,
                ),
            )
        if not target_accepted:
            decline_effects = tuple(
                _format_effect(p, actor_name=actor.actor_name, target_name=target_name)
                for p in pipeline.on_failure
            )
            return CustomCommandExecutionResult(
                status="declined",
                command_id=cmd.command_id,
                branch="failure",
                effects=decline_effects,
            )
        branch = "success"

    elif step.kind in {"skill_check", "contested_check"}:
        if skill_check_resolver is not None:
            branch = skill_check_resolver(cmd, actor, target_id)
        else:
            digest = hashlib.sha256(
                f"check:{cmd.command_id}:{actor.actor_id}:{target_id}".encode()
            ).digest()
            roll = (int.from_bytes(digest[:2], "big") % 20) + 1
            branch = "success" if roll >= 12 else ("partial" if roll >= 7 else "failure")

    elif step.kind == "random_table":
        if table_roll_fn is not None:
            table_roll = table_roll_fn(cmd, step.table_die_sides)
        else:
            digest = hashlib.sha256(
                f"table:{cmd.command_id}:{actor.actor_id}:{actor.room_id}".encode()
            ).digest()
            table_roll = (int.from_bytes(digest[:2], "big") % step.table_die_sides) + 1

        matched_branch: OutcomeBranch = "failure"
        for outcome in step.table_outcomes:
            if outcome.min_roll <= table_roll <= outcome.max_roll:
                matched_branch = outcome.branch
                break
        branch = matched_branch

    # Step 3: Ordered deterministic payloads
    if branch == "success":
        raw_payloads = pipeline.on_success
    elif branch == "partial":
        raw_payloads = pipeline.on_partial
    else:
        raw_payloads = pipeline.on_failure

    effects = tuple(
        _format_effect(p, actor_name=actor.actor_name, target_name=target_name)
        for p in raw_payloads
    )

    # Step 4: Optional interruptible channeling countdown gate (zero sleep())
    if pipeline.channeling is not None and branch in {"success", "partial"}:
        ch_spec = pipeline.channeling
        comp_effects = tuple(
            _format_effect(p, actor_name=actor.actor_name, target_name=target_name)
            for p in ch_spec.completion_effects
        )
        task = ChannelingTaskSpec(
            command_id=cmd.command_id,
            actor_id=actor.actor_id,
            target_id=target_id,
            target_name=target_name,
            channel_condition_id=ch_spec.channel_condition_id,
            remaining_turns=ch_spec.duration_turns,
            interrupt_on_move=ch_spec.interrupt_on_move,
            interrupt_on_damage=ch_spec.interrupt_on_damage,
            completion_effects=comp_effects,
        )
        return CustomCommandExecutionResult(
            status="channeling_started",
            command_id=cmd.command_id,
            branch=branch,
            costs_deducted=costs_deducted,
            table_roll=table_roll,
            effects=effects,
            channeling_task=task,
        )

    return CustomCommandExecutionResult(
        status="executed",
        command_id=cmd.command_id,
        branch=branch,
        costs_deducted=costs_deducted,
        table_roll=table_roll,
        effects=effects,
    )


def tick_channeling_task(
    task: ChannelingTaskSpec,
    *,
    moved: bool = False,
    damaged: bool = False,
) -> tuple[
    Literal["channeling", "completed", "interrupted"],
    ChannelingTaskSpec | None,
    tuple[EmittedCommandEffect, ...],
]:
    """Advance or interrupt an active ECA Step 4 channeling task without sleeping."""
    if (moved and task.interrupt_on_move) or (damaged and task.interrupt_on_damage):
        return "interrupted", None, ()
    remaining = task.remaining_turns - 1
    if remaining <= 0:
        return "completed", None, task.completion_effects
    updated = task.model_copy(update={"remaining_turns": remaining})
    return "channeling", updated, ()
