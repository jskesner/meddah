"""Deterministic <5ms MUD command lexer, Two-Tier router, prosody & mixed-pose DSL."""

from __future__ import annotations

import hashlib
import re
from collections import deque
from collections.abc import Callable, Mapping, Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.mud_parser.social_emote_library import (
    EmoteSpec,
    SemanticValence,
    infer_tone_valence,
    render_emote,
    resolve_emote,
)

ProsodyKind = Literal["plain", "italic", "bold", "all_caps", "pause", "chant"]
MudCommandCategory = Literal[
    "movement",
    "observation",
    "inventory",
    "covert",
    "time_control",
    "vm_action",
    "roll",
    "communication",
    "emote",
    "social_emote",
    "diegetic_comm",
    "custom_command",
    "alias",
    "meta",
    "narrative_fallback",
]
TierRoute = Literal["tier_1_deterministic", "tier_2_narrative"]

MOVEMENT_VERBS: frozenset[str] = frozenset(
    {
        "n",
        "s",
        "e",
        "w",
        "ne",
        "nw",
        "se",
        "sw",
        "u",
        "d",
        "north",
        "south",
        "east",
        "west",
        "northeast",
        "northwest",
        "southeast",
        "southwest",
        "up",
        "down",
        "in",
        "out",
        "enter",
        "exit",
        "go",
    }
)
OBSERVATION_VERBS: frozenset[str] = frozenset({"look", "l", "examine", "ex", "search"})
INVENTORY_VERBS: frozenset[str] = frozenset(
    {"inventory", "inv", "i", "equip", "unequip", "wear", "remove", "outfit", "take", "get", "drop"}
)
COVERT_VERBS: frozenset[str] = frozenset({"hide", "sneak", "steal", "plant", "disguise"})
TIME_VERBS: frozenset[str] = frozenset({"timeskip", "wait"})
ROLL_VERBS: frozenset[str] = frozenset({"roll", "flip", "coin"})
VM_ACTION_VERBS: frozenset[str] = frozenset(
    {"use", "cast", "attack", "strike", "defend", "dodge", "dash", "assist"}
)
META_VERBS: frozenset[str] = frozenset({"who", "status", "sheet", "journal", "codex", "help", "?"})
BUILTIN_MEDIUM_VERBS: frozenset[str] = frozenset(
    {
        "radio",
        "telepathy",
        "bond",
        "pray",
        "commune",
        "send",
        "aether",
        "bbs",
        "watch",
        "broadcast",
        "courier",
        "raven",
        "touch-helmet",
        "touch_helmet",
        "sign",
        "comms",
    }
)

_ALL_CAPS_RE = re.compile(r"\b[A-Z]{2,}\b")
_MULTISPACE_RE = re.compile(r"\s{2,}")
_PROSODY_TOKEN_RE = re.compile(r"(\*\*[^*]+\*\*|\*[^*]+\*|~[^~]+~|\[pause\]|\.\.\.|--)")
_PA_PREFIX_RE = re.compile(r"^\(\s*pa\s*:\s*([^)]+?)\s*\)\s*", re.IGNORECASE)
_TONE_PREFIX_RE = re.compile(r"^\(\s*([^)]+?)\s*\)\s*")
_BRACKET_LANG_RE = re.compile(r"^\[\s*([A-Za-z0-9_-]+)\s*\]\s*")
_IN_LANG_RE = re.compile(r"^in\s+([A-Za-z0-9_-]+)\s+", re.IGNORECASE)
_TARGET_AT_RE = re.compile(r"^@([A-Za-z0-9_-]+)(?:\s+(.*))?$")


class ProsodySpan(BaseModel):
    """Single inline emphasis, pause, or chanted segment inside speech."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: ProsodyKind
    text: str
    pause_ms: int = 0


class ParsedSpeech(BaseModel):
    """Parsed dialogue payload including emphasis spans, tone, language, and dual-layer cant."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    raw_text: str
    clean_text: str
    spans: tuple[ProsodySpan, ...] = ()
    tone: str | None = None
    valence: SemanticValence = "neutral"
    language_id: str | None = None
    cant_subtext: str | None = None
    pa_mode: str | None = None


class PoseBeat(BaseModel):
    """Single clause inside a mixed action + speech roleplay pose."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["action", "speech", "target_ref", "mannerism"]
    text: str
    target_token: str | None = None
    speech: ParsedSpeech | None = None


class ParsedMudCommand(BaseModel):
    """Structured Two-Tier command routing record produced in <5ms with zero AI calls."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    raw_input: str
    category: MudCommandCategory
    verb: str
    args: tuple[str, ...] = ()
    target_token: str | None = None
    channel_alias: str | None = None
    language_id: str | None = None
    tone: str | None = None
    pa_mode: str | None = None
    adverb: str | None = None
    speech: ParsedSpeech | None = None
    pose_beats: tuple[PoseBeat, ...] = ()
    valence: SemanticValence = "neutral"
    flags: tuple[str, ...] = ()
    tier_route: TierRoute = "tier_1_deterministic"


class WhisperEavesdropListener(BaseModel):
    """Bystander hearing profile for non-interrupting whisper eavesdrop checks."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    entity_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    passive_observation: int = 0
    active_eavesdrop_target_id: str | None = None
    keen_hearing: bool = False
    roll_bonus: int = 0


class WhisperDelivery(BaseModel):
    """Per-listener whisper visibility outcome without interrupting popup prompts."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    recipient_id: str
    role: Literal["actor", "target", "gm", "eavesdropper_full", "eavesdropper_partial", "observer"]
    rendered_text: str
    leaked_speech: str | None = None


class RoomTopologyEdge(BaseModel):
    """Directed exit edge used to compute multi-room acoustic bleed for shouts."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    from_room_id: str = Field(min_length=1)
    to_room_id: str = Field(min_length=1)
    direction_label: str = Field(min_length=1)
    from_room_name: str = Field(min_length=1)
    is_sealed: bool = False
    is_vertical_shaft: bool = False


class ShoutPropagationResult(BaseModel):
    """1-2 hop acoustic bleed and stealth/alert consequences for shout/yell."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    room_text: str
    adjacent_bleed: dict[str, str] = Field(default_factory=dict)
    breaks_stealth: bool = True
    alert_clock_delta: int = 1


class RenderedPose(BaseModel):
    """Perspective-adapted pose output plus separated TTS vs Narrator speech segments."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    to_room: str
    per_target_views: dict[str, str] = Field(default_factory=dict)
    tts_dialogue_segments: tuple[str, ...] = ()
    narrator_action_segments: tuple[str, ...] = ()
    mentioned_targets: tuple[str, ...] = ()
    valence: SemanticValence = "neutral"


def _strip_matching_quotes(text: str) -> str:
    stripped = text.strip()
    if len(stripped) >= 2 and (
        (stripped[0] == '"' and stripped[-1] == '"') or (stripped[0] == "'" and stripped[-1] == "'")
    ):
        return stripped[1:-1]
    return stripped


def _split_plain_caps(segment: str, out: list[ProsodySpan]) -> None:
    pos = 0
    for match in _ALL_CAPS_RE.finditer(segment):
        if match.start() > pos:
            out.append(ProsodySpan(kind="plain", text=segment[pos : match.start()]))
        out.append(ProsodySpan(kind="all_caps", text=match.group(0)))
        pos = match.end()
    if pos < len(segment):
        out.append(ProsodySpan(kind="plain", text=segment[pos:]))


def parse_prosody(
    text: str,
    *,
    tone: str | None = None,
    language_id: str | None = None,
    pa_mode: str | None = None,
) -> ParsedSpeech:
    """Parse inline prosody (*italic*, **bold**, ALL CAPS, pauses, ~chant~) & cant dual-layer."""
    raw = text.strip()
    cant_subtext: str | None = None
    surface_raw = raw

    if "|" in raw:
        surface_part, sub_part = raw.split("|", 1)
        surface_clean = _strip_matching_quotes(surface_part)
        sub_clean = _strip_matching_quotes(sub_part)
        if sub_clean:
            surface_raw = surface_clean
            cant_subtext = sub_clean
    else:
        surface_raw = _strip_matching_quotes(raw)

    spans: list[ProsodySpan] = []
    clean_parts: list[str] = []
    pos = 0

    for match in _PROSODY_TOKEN_RE.finditer(surface_raw):
        if match.start() > pos:
            plain_chunk = surface_raw[pos : match.start()]
            _split_plain_caps(plain_chunk, spans)
            clean_parts.append(plain_chunk)

        tok = match.group(0)
        if tok.startswith("**") and tok.endswith("**"):
            inner = tok[2:-2]
            spans.append(ProsodySpan(kind="bold", text=inner))
            clean_parts.append(inner)
        elif tok.startswith("*") and tok.endswith("*"):
            inner = tok[1:-1]
            spans.append(ProsodySpan(kind="italic", text=inner))
            clean_parts.append(inner)
        elif tok.startswith("~") and tok.endswith("~"):
            inner = tok[1:-1]
            spans.append(ProsodySpan(kind="chant", text=inner))
            clean_parts.append(inner)
        elif tok == "[pause]":
            spans.append(ProsodySpan(kind="pause", text="[pause]", pause_ms=500))
            clean_parts.append(" ")
        elif tok in {"...", "--"}:
            spans.append(ProsodySpan(kind="pause", text=tok, pause_ms=350))
            clean_parts.append(tok)
        pos = match.end()

    if pos < len(surface_raw):
        tail_chunk = surface_raw[pos:]
        _split_plain_caps(tail_chunk, spans)
        clean_parts.append(tail_chunk)

    clean_text = _MULTISPACE_RE.sub(" ", "".join(clean_parts)).strip()
    return ParsedSpeech(
        raw_text=raw,
        clean_text=clean_text,
        spans=tuple(spans),
        tone=tone,
        valence=infer_tone_valence(tone),
        language_id=language_id,
        cant_subtext=cant_subtext,
        pa_mode=pa_mode,
    )


def parse_mixed_pose(
    raw_body: str,
    *,
    possessive: bool = False,
) -> tuple[tuple[PoseBeat, ...], tuple[str, ...], SemanticValence]:
    """Parse mixed (mannerism), @target, and "quoted speech" clauses into structured beats."""
    del possessive
    body = raw_body.strip()
    beats: list[PoseBeat] = []
    targets: list[str] = []
    seen_targets: set[str] = set()
    valence: SemanticValence = "neutral"

    action_buf: list[str] = []
    idx = 0
    n = len(body)

    def _flush_action() -> None:
        if action_buf:
            chunk = "".join(action_buf)
            if chunk:
                beats.append(PoseBeat(kind="action", text=chunk))
            action_buf.clear()

    while idx < n:
        ch = body[idx]
        if ch == '"':
            end_q = body.find('"', idx + 1)
            if end_q != -1:
                _flush_action()
                quoted = body[idx + 1 : end_q]
                speech = parse_prosody(quoted)
                beats.append(PoseBeat(kind="speech", text=quoted, speech=speech))
                idx = end_q + 1
                continue
        elif ch == "(":
            end_p = body.find(")", idx + 1)
            if end_p != -1:
                _flush_action()
                inner = body[idx + 1 : end_p].strip()
                beats.append(PoseBeat(kind="mannerism", text=inner))
                if valence == "neutral":
                    inferred = infer_tone_valence(inner)
                    if inferred != "neutral":
                        valence = inferred
                idx = end_p + 1
                continue
        elif ch == "@":
            match = re.match(r"@([A-Za-z0-9_-]+)", body[idx:])
            if match is not None:
                _flush_action()
                tid = match.group(1)
                if tid not in seen_targets:
                    seen_targets.add(tid)
                    targets.append(tid)
                beats.append(PoseBeat(kind="target_ref", text=f"@{tid}", target_token=tid))
                idx += len(match.group(0))
                continue

        action_buf.append(ch)
        idx += 1

    _flush_action()
    return tuple(beats), tuple(targets), valence


def _render_beat_sequence(
    actor_hypertext: str,
    beats: Sequence[PoseBeat],
    *,
    entity_names: Mapping[str, str],
    viewer_target_id: str | None,
    possessive: bool,
) -> str:
    parts: list[str] = []
    for beat in beats:
        if beat.kind == "mannerism":
            parts.append(f"({beat.text})")
        elif beat.kind == "speech":
            parts.append(f'"{beat.text}"')
        elif beat.kind == "target_ref" and beat.target_token is not None:
            if viewer_target_id is not None and beat.target_token == viewer_target_id:
                parts.append("**you**")
            else:
                disp = entity_names.get(beat.target_token, beat.target_token)
                parts.append(f"[[entity:{beat.target_token}|{disp}]]")
        else:
            parts.append(beat.text)

    body_text = "".join(parts).strip()
    if not body_text:
        return actor_hypertext
    if possessive or body_text.startswith(("'s", "'", ",", ".", "!", "?")):
        if body_text.startswith(("'s", "'", ",", ".", "!", "?")):
            return f"{actor_hypertext}{body_text}"
        return f"{actor_hypertext}{body_text}"
    return f"{actor_hypertext} {body_text}"


def render_mixed_pose(
    actor_id: str,
    actor_name: str,
    beats: Sequence[PoseBeat],
    *,
    entity_names: Mapping[str, str] | None = None,
    possessive: bool = False,
) -> RenderedPose:
    """Render mixed pose beats into room hypertext, target views, and split TTS/Narrator text."""
    names = dict(entity_names or {})
    actor_tag = f"[[entity:{actor_id}|{actor_name}]]"

    to_room = _render_beat_sequence(
        actor_tag,
        beats,
        entity_names=names,
        viewer_target_id=None,
        possessive=possessive,
    )

    mentioned: list[str] = []
    seen_targets: set[str] = set()
    tts_segments: list[str] = []
    narrator_parts: list[str] = []
    valence: SemanticValence = "neutral"

    for beat in beats:
        if beat.kind == "target_ref" and beat.target_token is not None:
            if beat.target_token not in seen_targets:
                seen_targets.add(beat.target_token)
                mentioned.append(beat.target_token)
            narrator_parts.append(names.get(beat.target_token, beat.target_token))
        elif beat.kind == "speech" and beat.speech is not None:
            tts_segments.append(beat.speech.clean_text)
        elif beat.kind == "mannerism":
            narrator_parts.append(f"({beat.text})")
            if valence == "neutral":
                cand = infer_tone_valence(beat.text)
                if cand != "neutral":
                    valence = cand
        else:
            narrator_parts.append(beat.text)

    per_target_views: dict[str, str] = {
        tid: _render_beat_sequence(
            actor_tag,
            beats,
            entity_names=names,
            viewer_target_id=tid,
            possessive=possessive,
        )
        for tid in mentioned
    }

    narrator_joined = _MULTISPACE_RE.sub(" ", "".join(narrator_parts)).strip()
    narrator_segments: tuple[str, ...] = (narrator_joined,) if narrator_joined else ()

    return RenderedPose(
        to_room=to_room,
        per_target_views=per_target_views,
        tts_dialogue_segments=tuple(tts_segments),
        narrator_action_segments=narrator_segments,
        mentioned_targets=tuple(mentioned),
        valence=valence,
    )


def _extract_inline_modifiers(
    text: str,
    *,
    default_language: str | None = None,
) -> tuple[str | None, str | None, str | None, str]:
    """Extract optional `in <lang>`, `[<lang>]`, `(pa: <mode>)`, and `(tone)` prefixes."""
    rem = text.lstrip()
    language_id = default_language
    tone: str | None = None
    pa_mode: str | None = None

    changed = True
    while changed and rem:
        changed = False
        m_pa = _PA_PREFIX_RE.match(rem)
        if m_pa is not None:
            pa_mode = m_pa.group(1).strip().lower()
            rem = rem[m_pa.end() :].lstrip()
            changed = True
            continue
        m_lang_br = _BRACKET_LANG_RE.match(rem)
        if m_lang_br is not None:
            language_id = m_lang_br.group(1).strip().lower()
            rem = rem[m_lang_br.end() :].lstrip()
            changed = True
            continue
        m_in_lang = _IN_LANG_RE.match(rem)
        if m_in_lang is not None:
            language_id = m_in_lang.group(1).strip().lower()
            rem = rem[m_in_lang.end() :].lstrip()
            changed = True
            continue
        m_tone = _TONE_PREFIX_RE.match(rem)
        if m_tone is not None and tone is None:
            cand = m_tone.group(1).strip()
            if cand.lower().startswith("pa:"):
                pa_mode = cand[3:].strip().lower()
            else:
                tone = cand
            rem = rem[m_tone.end() :].lstrip()
            changed = True
            continue

    return language_id, tone, pa_mode, rem


def _expand_alias(
    raw_input: str,
    client_aliases: Mapping[str, str] | None,
    *,
    max_depth: int = 4,
) -> tuple[str, bool]:
    if not client_aliases:
        return raw_input, False
    current = raw_input.strip()
    expanded = False

    for _ in range(max_depth):
        if not current:
            break
        parts = current.split(None, 1)
        head = parts[0].lstrip("/").lower()
        if head in {"alias", "unalias", "aliases"}:
            break
        template = client_aliases.get(head) or client_aliases.get(parts[0])
        if template is None:
            break
        arg_tokens = parts[1].split() if len(parts) > 1 else []
        arg_tail = parts[1] if len(parts) > 1 else ""
        result = template
        used_positional = False
        for idx in range(1, 10):
            token_val = arg_tokens[idx - 1] if idx - 1 < len(arg_tokens) else ""
            for marker in (f"@{idx}", f"${idx}"):
                if marker in result:
                    result = result.replace(marker, token_val)
                    used_positional = True
        for all_marker in ("@*", "$*"):
            if all_marker in result:
                result = result.replace(all_marker, arg_tail)
                used_positional = True
        if not used_positional and arg_tail:
            result = f"{result} {arg_tail}"
        current = _MULTISPACE_RE.sub(" ", result).strip()
        expanded = True
    return current, expanded


def _parse_social_emote_args(rest: str) -> tuple[str | None, str | None, str | None]:
    """Parse `<@target> <adverb> "<speech>"` arguments in any partial combination."""
    rem = rest.strip()
    if not rem:
        return None, None, None

    speech: str | None = None
    first_quote = rem.find('"')
    if first_quote != -1:
        end_quote = rem.rfind('"')
        if end_quote > first_quote:
            speech = rem[first_quote + 1 : end_quote].strip()
            rem = f"{rem[:first_quote]} {rem[end_quote + 1 :]}".strip()

    target_token: str | None = None
    adverbs: list[str] = []
    for tok in rem.split():
        if tok.startswith("@") and len(tok) > 1 and target_token is None:
            target_token = tok[1:]
        else:
            adverbs.append(tok)

    adverb = " ".join(adverbs).strip() or None
    return target_token, adverb, speech


def _extract_target_and_rest(tail: str) -> tuple[str | None, str]:
    cleaned = tail.strip()
    if not cleaned:
        return None, ""
    if cleaned.lower().startswith("to "):
        cleaned = cleaned[3:].lstrip()
    if cleaned.startswith("@"):
        m = _TARGET_AT_RE.match(cleaned)
        if m is not None:
            return m.group(1), (m.group(2) or "").strip()
    parts = cleaned.split(None, 1)
    target = parts[0].lstrip("@")
    rest = parts[1].strip() if len(parts) > 1 else ""
    return target, rest


def parse_mud_command(
    raw_input: str,
    *,
    custom_verbs: Sequence[str] = (),
    custom_emotes: Mapping[str, EmoteSpec] | None = None,
    medium_verbs: Sequence[str] = (),
    client_aliases: Mapping[str, str] | None = None,
    default_language: str | None = None,
) -> ParsedMudCommand:
    """Deterministically lex and route any MUD input in <5ms (Zero AI calls)."""
    stripped = raw_input.strip()
    expanded_input, was_alias = _expand_alias(stripped, client_aliases)
    flags: list[str] = ["alias_expanded"] if was_alias else []

    if not expanded_input:
        return ParsedMudCommand(
            raw_input=raw_input,
            category="meta",
            verb="noop",
            flags=tuple(flags),
        )

    # 1. Non-word prefix shortcuts checked BEFORE slash stripping (so // works as OOC)
    if expanded_input.startswith("//"):
        body = expanded_input[2:].strip()
        speech = parse_prosody(body) if body else None
        return ParsedMudCommand(
            raw_input=raw_input,
            category="communication",
            verb="ooc",
            speech=speech,
            flags=tuple(flags),
        )

    if expanded_input.startswith("::'s") or expanded_input.startswith(":'s"):
        prefix_len = 4 if expanded_input.startswith("::'s") else 3
        body = f"'s {expanded_input[prefix_len:].lstrip()}".strip()
        beats, _targets, valence = parse_mixed_pose(body, possessive=True)
        return ParsedMudCommand(
            raw_input=raw_input,
            category="emote",
            verb="emote",
            pose_beats=beats,
            valence=valence,
            flags=(*flags, "possessive"),
        )

    if expanded_input.startswith("::"):
        body = expanded_input[2:].strip()
        beats, _targets, valence = parse_mixed_pose(body, possessive=True)
        return ParsedMudCommand(
            raw_input=raw_input,
            category="emote",
            verb="emote",
            pose_beats=beats,
            valence=valence,
            flags=(*flags, "possessive"),
        )

    if expanded_input.startswith(":"):
        body = expanded_input[1:].strip()
        beats, _targets, valence = parse_mixed_pose(body)
        return ParsedMudCommand(
            raw_input=raw_input,
            category="emote",
            verb="emote",
            pose_beats=beats,
            valence=valence,
            flags=tuple(flags),
        )

    if expanded_input.startswith("'"):
        lang, tone, pa_mode, msg_body = _extract_inline_modifiers(
            expanded_input[1:], default_language=default_language
        )
        speech = parse_prosody(msg_body, tone=tone, language_id=lang, pa_mode=pa_mode)
        return ParsedMudCommand(
            raw_input=raw_input,
            category="communication",
            verb="say",
            language_id=lang,
            tone=tone,
            pa_mode=pa_mode,
            speech=speech,
            valence=speech.valence,
            flags=tuple(flags),
        )

    if expanded_input.startswith('"'):
        speech = parse_prosody(expanded_input, language_id=default_language)
        return ParsedMudCommand(
            raw_input=raw_input,
            category="communication",
            verb="say",
            language_id=default_language,
            speech=speech,
            valence=speech.valence,
            flags=tuple(flags),
        )

    m_lang_direct = _BRACKET_LANG_RE.match(expanded_input)
    if m_lang_direct is not None:
        lang = m_lang_direct.group(1).strip().lower()
        rest = expanded_input[m_lang_direct.end() :]
        _, tone, pa_mode, msg_body = _extract_inline_modifiers(rest, default_language=lang)
        speech = parse_prosody(msg_body, tone=tone, language_id=lang, pa_mode=pa_mode)
        return ParsedMudCommand(
            raw_input=raw_input,
            category="communication",
            verb="say",
            language_id=lang,
            tone=tone,
            pa_mode=pa_mode,
            speech=speech,
            valence=speech.valence,
            flags=tuple(flags),
        )

    if expanded_input.startswith("@"):
        m_at = _TARGET_AT_RE.match(expanded_input)
        if m_at is not None and m_at.group(2):
            target = m_at.group(1)
            lang, tone, pa_mode, msg_body = _extract_inline_modifiers(
                m_at.group(2), default_language=default_language
            )
            speech = parse_prosody(msg_body, tone=tone, language_id=lang, pa_mode=pa_mode)
            return ParsedMudCommand(
                raw_input=raw_input,
                category="communication",
                verb="say_to",
                target_token=target,
                language_id=lang,
                tone=tone,
                pa_mode=pa_mode,
                speech=speech,
                valence=speech.valence,
                flags=tuple(flags),
            )

    # 2. Normalized leading `/` for command palette invocations
    normalized = (
        expanded_input[1:].lstrip()
        if expanded_input.startswith("/") and not expanded_input.startswith("//")
        else expanded_input
    )
    parts = normalized.split(None, 1)
    verb_raw = parts[0].lower()
    tail = parts[1].strip() if len(parts) > 1 else ""

    # Multi-word commands checked early
    if verb_raw == "say" and tail.lower().startswith("to "):
        target, rest = _extract_target_and_rest(tail)
        lang, tone, pa_mode, msg_body = _extract_inline_modifiers(
            rest, default_language=default_language
        )
        speech = parse_prosody(msg_body, tone=tone, language_id=lang, pa_mode=pa_mode)
        return ParsedMudCommand(
            raw_input=raw_input,
            category="communication",
            verb="say_to",
            target_token=target,
            language_id=lang,
            tone=tone,
            pa_mode=pa_mode,
            speech=speech,
            valence=speech.valence,
            flags=tuple(flags),
        )

    if verb_raw == "suit":
        sub_parts = tail.split(None, 1)
        sub_cmd = sub_parts[0].lower() if sub_parts else ""
        sub_arg = sub_parts[1].strip() if len(sub_parts) > 1 else ""
        if sub_cmd == "voice":
            return ParsedMudCommand(
                raw_input=raw_input,
                category="diegetic_comm",
                verb="suit_voice",
                args=tuple(sub_arg.split()) if sub_arg else (),
                pa_mode=sub_arg or None,
                flags=tuple(flags),
            )
        if sub_cmd == "speaker":
            return ParsedMudCommand(
                raw_input=raw_input,
                category="diegetic_comm",
                verb="suit_speaker",
                args=tuple(sub_arg.split()) if sub_arg else (),
                flags=tuple(flags),
            )

    if verb_raw in {"alias", "unalias", "aliases"}:
        return ParsedMudCommand(
            raw_input=raw_input,
            category="alias",
            verb=verb_raw,
            args=(tail,) if tail and verb_raw == "alias" else tuple(tail.split()),
            flags=tuple(flags),
        )

    if verb_raw in MOVEMENT_VERBS:
        return ParsedMudCommand(
            raw_input=raw_input,
            category="movement",
            verb=verb_raw,
            args=tuple(tail.split()) if tail else (),
            flags=tuple(flags),
        )

    if verb_raw in OBSERVATION_VERBS:
        target = tail[1:] if tail.startswith("@") else (tail or None)
        return ParsedMudCommand(
            raw_input=raw_input,
            category="observation",
            verb=verb_raw,
            args=tuple(tail.split()) if tail else (),
            target_token=target,
            flags=tuple(flags),
        )

    if verb_raw in INVENTORY_VERBS:
        return ParsedMudCommand(
            raw_input=raw_input,
            category="inventory",
            verb=verb_raw,
            args=tuple(tail.split()) if tail else (),
            flags=tuple(flags),
        )

    if verb_raw in COVERT_VERBS:
        arg_list = tail.split() if tail else []
        target_tok: str | None = None
        for a in arg_list:
            if a.startswith("@") and len(a) > 1:
                target_tok = a[1:]
                break
        return ParsedMudCommand(
            raw_input=raw_input,
            category="covert",
            verb=verb_raw,
            args=tuple(arg_list),
            target_token=target_tok,
            flags=tuple(flags),
        )

    if verb_raw in TIME_VERBS:
        return ParsedMudCommand(
            raw_input=raw_input,
            category="time_control",
            verb=verb_raw,
            args=tuple(tail.split()) if tail else (),
            flags=tuple(flags),
        )

    if verb_raw in ROLL_VERBS:
        return ParsedMudCommand(
            raw_input=raw_input,
            category="roll",
            verb=verb_raw,
            args=tuple(tail.split()) if tail else (),
            flags=tuple(flags),
        )

    if verb_raw in VM_ACTION_VERBS:
        arg_list = tail.split() if tail else []
        target_tok: str | None = None
        for a in arg_list:
            if a.startswith("@") and len(a) > 1:
                target_tok = a[1:]
                break
        return ParsedMudCommand(
            raw_input=raw_input,
            category="vm_action",
            verb=verb_raw,
            args=tuple(arg_list),
            target_token=target_tok,
            flags=tuple(flags),
        )

    # Core communication verbs
    if verb_raw == "say":
        lang, tone, pa_mode, msg_body = _extract_inline_modifiers(
            tail, default_language=default_language
        )
        speech = parse_prosody(msg_body, tone=tone, language_id=lang, pa_mode=pa_mode)
        return ParsedMudCommand(
            raw_input=raw_input,
            category="communication",
            verb="say",
            language_id=lang,
            tone=tone,
            pa_mode=pa_mode,
            speech=speech,
            valence=speech.valence,
            flags=tuple(flags),
        )

    if verb_raw == "to":
        target, rest = _extract_target_and_rest(tail)
        lang, tone, pa_mode, msg_body = _extract_inline_modifiers(
            rest, default_language=default_language
        )
        speech = parse_prosody(msg_body, tone=tone, language_id=lang, pa_mode=pa_mode)
        return ParsedMudCommand(
            raw_input=raw_input,
            category="communication",
            verb="say_to",
            target_token=target,
            language_id=lang,
            tone=tone,
            pa_mode=pa_mode,
            speech=speech,
            valence=speech.valence,
            flags=tuple(flags),
        )

    if verb_raw == "ask":
        target, rest = _extract_target_and_rest(tail)
        topic = rest[6:].strip() if rest.lower().startswith("about ") else rest
        speech = parse_prosody(topic, language_id=default_language) if topic else None
        return ParsedMudCommand(
            raw_input=raw_input,
            category="communication",
            verb="ask",
            target_token=target,
            args=(topic,) if topic else (),
            language_id=default_language,
            speech=speech,
            flags=tuple(flags),
        )

    if verb_raw in {"whisper", "wh"}:
        target, rest = _extract_target_and_rest(tail)
        lang, tone, pa_mode, msg_body = _extract_inline_modifiers(
            rest, default_language=default_language
        )
        speech = parse_prosody(msg_body, tone=tone, language_id=lang, pa_mode=pa_mode)
        return ParsedMudCommand(
            raw_input=raw_input,
            category="communication",
            verb="whisper",
            target_token=target,
            language_id=lang,
            tone=tone,
            pa_mode=pa_mode,
            speech=speech,
            valence=speech.valence,
            flags=tuple(flags),
        )

    if verb_raw in {"shout", "yell"}:
        lang, tone, pa_mode, msg_body = _extract_inline_modifiers(
            tail, default_language=default_language
        )
        speech = parse_prosody(msg_body, tone=tone, language_id=lang, pa_mode=pa_mode)
        return ParsedMudCommand(
            raw_input=raw_input,
            category="communication",
            verb="shout",
            language_id=lang,
            tone=tone,
            pa_mode=pa_mode,
            speech=speech,
            valence=speech.valence if speech.valence != "neutral" else "tactical_signal",
            flags=tuple(flags),
        )

    if verb_raw == "tell":
        target, rest = _extract_target_and_rest(tail)
        speech = parse_prosody(rest)
        return ParsedMudCommand(
            raw_input=raw_input,
            category="communication",
            verb="tell",
            target_token=target,
            speech=speech,
            valence=speech.valence,
            flags=tuple(flags),
        )

    if verb_raw == "ooc":
        speech = parse_prosody(tail)
        return ParsedMudCommand(
            raw_input=raw_input,
            category="communication",
            verb="ooc",
            speech=speech,
            flags=tuple(flags),
        )

    if verb_raw in {"party", "p"}:
        lang, tone, pa_mode, msg_body = _extract_inline_modifiers(
            tail, default_language=default_language
        )
        speech = parse_prosody(msg_body, tone=tone, language_id=lang, pa_mode=pa_mode)
        return ParsedMudCommand(
            raw_input=raw_input,
            category="communication",
            verb="party",
            channel_alias="party",
            language_id=lang,
            tone=tone,
            pa_mode=pa_mode,
            speech=speech,
            valence=speech.valence,
            flags=tuple(flags),
        )

    if verb_raw == "eavesdrop":
        target = tail[1:] if tail.startswith("@") else (tail or None)
        return ParsedMudCommand(
            raw_input=raw_input,
            category="communication",
            verb="eavesdrop",
            target_token=target,
            flags=tuple(flags),
        )

    if verb_raw in {"act", "emote", "pose"}:
        beats, _targets, valence = parse_mixed_pose(tail)
        return ParsedMudCommand(
            raw_input=raw_input,
            category="emote",
            verb="emote",
            pose_beats=beats,
            valence=valence,
            flags=tuple(flags),
        )

    custom_verb_set = {v.lower() for v in custom_verbs}
    if verb_raw in custom_verb_set:
        arg_list = tail.split() if tail else []
        target_tok = None
        for a in arg_list:
            if a.startswith("@") and len(a) > 1:
                target_tok = a[1:]
                break
        return ParsedMudCommand(
            raw_input=raw_input,
            category="custom_command",
            verb=verb_raw,
            args=tuple(arg_list),
            target_token=target_tok,
            flags=tuple(flags),
        )

    medium_verb_set = BUILTIN_MEDIUM_VERBS | {v.lower() for v in medium_verbs}
    # Handle `listen <station>` as diegetic_comm, bare `listen [@target]` as social emote
    is_listen_station = verb_raw == "listen" and bool(tail) and not tail.startswith(("@", '"', "("))
    if verb_raw in medium_verb_set or is_listen_station:
        normalized_verb = verb_raw.replace("-", "_")
        channel_alias: str | None = None
        target_tok = None
        rest = tail

        if normalized_verb == "radio":
            sub = rest.split(None, 1)
            if sub and sub[0].lower() == "save":
                return ParsedMudCommand(
                    raw_input=raw_input,
                    category="diegetic_comm",
                    verb="radio_save",
                    args=tuple(sub[1].split()) if len(sub) > 1 else (),
                    flags=tuple(flags),
                )
            if sub and sub[0].lower() != "in" and not sub[0].startswith(('"', "(")):
                channel_alias = sub[0]
                rest = sub[1].strip() if len(sub) > 1 else ""
        elif normalized_verb in {"aether", "bbs", "watch", "listen", "broadcast"}:
            sub = rest.split(None, 1)
            if sub and not sub[0].startswith(("@", '"', "(")) and sub[0].lower() != "in":
                channel_alias = sub[0]
                rest = sub[1].strip() if len(sub) > 1 else ""
        elif normalized_verb in {
            "telepathy",
            "bond",
            "send",
            "courier",
            "raven",
            "touch_helmet",
            "sign",
        } and (
            rest.startswith("@")
            or (rest and not rest.startswith(('"', "(", "in ")) and len(rest.split()) > 1)
        ):
            target_tok, rest = _extract_target_and_rest(rest)

        lang, tone, pa_mode, msg_body = _extract_inline_modifiers(
            rest, default_language=default_language
        )
        speech = parse_prosody(msg_body, tone=tone, language_id=lang, pa_mode=pa_mode)
        return ParsedMudCommand(
            raw_input=raw_input,
            category="diegetic_comm",
            verb=normalized_verb,
            args=tuple(tail.split()) if tail else (),
            target_token=target_tok,
            channel_alias=channel_alias,
            language_id=lang,
            tone=tone,
            pa_mode=pa_mode,
            speech=speech,
            valence=speech.valence,
            flags=tuple(flags),
        )

    emote_spec = resolve_emote(verb_raw, custom_emotes)
    if emote_spec is not None:
        target_tok, adverb, speech_str = _parse_social_emote_args(tail)
        speech = (
            parse_prosody(speech_str, tone=adverb, language_id=default_language)
            if speech_str is not None
            else None
        )
        rendered = render_emote(
            emote_spec,
            "Actor",
            target_name=target_tok,
            adverb=adverb,
            speech=speech_str,
        )
        return ParsedMudCommand(
            raw_input=raw_input,
            category="social_emote",
            verb=emote_spec.verb,
            args=tuple(tail.split()) if tail else (),
            target_token=target_tok,
            adverb=adverb,
            speech=speech,
            valence=rendered.valence,
            flags=tuple(flags),
        )

    if verb_raw in META_VERBS:
        return ParsedMudCommand(
            raw_input=raw_input,
            category="meta",
            verb=verb_raw,
            args=tuple(tail.split()) if tail else (),
            flags=tuple(flags),
        )

    return ParsedMudCommand(
        raw_input=raw_input,
        category="narrative_fallback",
        verb=verb_raw,
        args=tuple(tail.split()) if tail else (),
        flags=tuple(flags),
        tier_route="tier_2_narrative",
    )


def _deterministic_eavesdrop_roll(actor_id: str, listener_id: str, message: str) -> int:
    digest = hashlib.sha256(f"{actor_id}:{listener_id}:{message}".encode()).digest()
    return (int.from_bytes(digest[:2], "big") % 20) + 1


def resolve_whisper_eavesdrop(
    actor_id: str,
    actor_name: str,
    target_id: str,
    target_name: str,
    message: str,
    listeners: Sequence[WhisperEavesdropListener],
    *,
    gm_ids: Sequence[str] = (),
    stealth_dc: int = 12,
    background_roll_fn: Callable[[WhisperEavesdropListener], int] | None = None,
) -> tuple[WhisperDelivery, ...]:
    """Deliver private whisper & silently evaluate non-interrupting passive/stance eavesdrop."""
    deliveries: list[WhisperDelivery] = []
    gm_set = set(gm_ids)

    for listener in listeners:
        if listener.entity_id == actor_id:
            deliveries.append(
                WhisperDelivery(
                    recipient_id=listener.entity_id,
                    role="actor",
                    rendered_text=f'You whisper to {target_name}, "{message}"',
                    leaked_speech=message,
                )
            )
        elif listener.entity_id == target_id:
            deliveries.append(
                WhisperDelivery(
                    recipient_id=listener.entity_id,
                    role="target",
                    rendered_text=f'{actor_name} leans in and whispers to you, "{message}"',
                    leaked_speech=message,
                )
            )
        elif listener.entity_id in gm_set:
            deliveries.append(
                WhisperDelivery(
                    recipient_id=listener.entity_id,
                    role="gm",
                    rendered_text=f'[GM] {actor_name} whispers to {target_name}, "{message}"',
                    leaked_speech=message,
                )
            )
        else:
            score = listener.passive_observation
            if listener.active_eavesdrop_target_id == actor_id or listener.keen_hearing:
                roll_val = (
                    background_roll_fn(listener)
                    if background_roll_fn is not None
                    else _deterministic_eavesdrop_roll(actor_id, listener.entity_id, message)
                )
                score = max(score, roll_val + listener.roll_bonus)

            if score >= stealth_dc + 5:
                deliveries.append(
                    WhisperDelivery(
                        recipient_id=listener.entity_id,
                        role="eavesdropper_full",
                        rendered_text=(
                            f"{actor_name} leans in toward {target_name}; "
                            f'you overhear cleanly: "{message}"'
                        ),
                        leaked_speech=message,
                    )
                )
            elif score >= stealth_dc:
                words = message.split()
                half = max(1, len(words) // 2)
                partial = " ".join(words[:half]) + ("..." if half < len(words) else "")
                deliveries.append(
                    WhisperDelivery(
                        recipient_id=listener.entity_id,
                        role="eavesdropper_partial",
                        rendered_text=(
                            f"{actor_name} leans in toward {target_name}; "
                            f'you catch a fragment: "{partial}"'
                        ),
                        leaked_speech=partial,
                    )
                )
            else:
                deliveries.append(
                    WhisperDelivery(
                        recipient_id=listener.entity_id,
                        role="observer",
                        rendered_text=(
                            f"{actor_name} leans in and whispers quietly to {target_name}."
                        ),
                        leaked_speech=None,
                    )
                )

    return tuple(deliveries)


def resolve_shout_propagation(
    actor_name: str,
    message: str,
    origin_room_id: str,
    edges: Sequence[RoomTopologyEdge],
    *,
    max_hops: int = 2,
) -> ShoutPropagationResult:
    """Compute 1-2 hop acoustic bleed across unsealed exits and vertical shafts."""
    clean_msg = _strip_matching_quotes(message)
    room_text = f'{actor_name} shouts, "**{clean_msg}**"'

    adjacency: dict[str, list[RoomTopologyEdge]] = {}
    for edge in edges:
        adjacency.setdefault(edge.from_room_id, []).append(edge)

    bleed: dict[str, str] = {}
    visited: set[str] = {origin_room_id}
    queue: deque[tuple[str, int]] = deque([(origin_room_id, 0)])

    while queue:
        cur_room, depth = queue.popleft()
        if depth >= max_hops:
            continue
        for edge in adjacency.get(cur_room, []):
            if edge.is_sealed or edge.to_room_id in visited:
                continue
            visited.add(edge.to_room_id)
            hop = depth + 1
            distance_hint = "nearby" if hop == 1 else "faintly in the distance"
            shaft_note = " (echoing through a vertical shaft)" if edge.is_vertical_shaft else ""
            bleed[edge.to_room_id] = (
                f"From the [[exit:{edge.direction_label}|{edge.from_room_name}]] "
                f"({edge.direction_label}, {distance_hint}){shaft_note}, "
                f"someone shouts, '{clean_msg}'"
            )
            queue.append((edge.to_room_id, hop))

    return ShoutPropagationResult(
        room_text=room_text,
        adjacent_bleed=bleed,
        breaks_stealth=True,
        alert_clock_delta=1,
    )
