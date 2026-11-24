"""Parameterized 3-perspective social emote library and semantic valence classifier."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SemanticValence = Literal[
    "neutral",
    "respectful_greeting",
    "warm_friendly",
    "affectionate_comfort",
    "cheerful_celebration",
    "hostile_intimidation",
    "sarcastic_taunt",
    "dismissive_scorn",
    "submissive_plea",
    "fearful_retreat",
    "curious_investigative",
    "weary_exasperated",
    "solemn_reverent",
    "deceptive_bluff",
    "tactical_signal",
]

EmoteCategory = Literal[
    "greetings_respect",
    "emotion_expression",
    "body_language",
    "tactical_atmospheric",
    "custom",
]

_MULTISPACE_RE = re.compile(r"\s{2,}")


class EmoteSpec(BaseModel):
    """Declarative parameterized 3-perspective social emote definition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    verb: str = Field(min_length=1)
    aliases: tuple[str, ...] = ()
    category: EmoteCategory = "emotion_expression"
    valence: SemanticValence = "neutral"
    no_target_actor: str = Field(min_length=1)
    no_target_room: str = Field(min_length=1)
    targeted_actor: str = Field(min_length=1)
    targeted_target: str = Field(min_length=1)
    targeted_room: str = Field(min_length=1)
    speech_verb_actor: str = "and say"
    speech_verb_third: str = "and says"
    requires: str = "true"
    audio_clip_ref: str | None = None
    vfx_cue: str | None = None


class RenderedPerspectives(BaseModel):
    """3-perspective social emote output ready for actor, target, and room streams."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    to_actor: str
    to_target: str | None = None
    to_room: str
    valence: SemanticValence = "neutral"
    spoken_segments: tuple[str, ...] = ()
    audio_clip_ref: str | None = None
    vfx_cue: str | None = None


TONE_VALENCE_MAP: dict[str, SemanticValence] = {
    "sarcastically": "sarcastic_taunt",
    "sarcastic": "sarcastic_taunt",
    "mockingly": "sarcastic_taunt",
    "mocking": "sarcastic_taunt",
    "smugly": "sarcastic_taunt",
    "dryly": "sarcastic_taunt",
    "coldly": "hostile_intimidation",
    "angrily": "hostile_intimidation",
    "rage": "hostile_intimidation",
    "menacingly": "hostile_intimidation",
    "threateningly": "hostile_intimidation",
    "fiercely": "hostile_intimidation",
    "grimly": "hostile_intimidation",
    "harshly": "hostile_intimidation",
    "venomously": "hostile_intimidation",
    "gently": "affectionate_comfort",
    "tenderly": "affectionate_comfort",
    "comfortingly": "affectionate_comfort",
    "softly": "affectionate_comfort",
    "affectionately": "affectionate_comfort",
    "warmly": "warm_friendly",
    "kindly": "warm_friendly",
    "friendly": "warm_friendly",
    "amiably": "warm_friendly",
    "cheerfully": "cheerful_celebration",
    "happily": "cheerful_celebration",
    "excitedly": "cheerful_celebration",
    "jubilantly": "cheerful_celebration",
    "respectfully": "respectful_greeting",
    "politely": "respectful_greeting",
    "courteously": "respectful_greeting",
    "formally": "respectful_greeting",
    "dismissively": "dismissive_scorn",
    "scornfully": "dismissive_scorn",
    "contemptuously": "dismissive_scorn",
    "pleadingly": "submissive_plea",
    "desperately": "submissive_plea",
    "meekly": "submissive_plea",
    "nervously": "fearful_retreat",
    "fearfully": "fearful_retreat",
    "trembling": "fearful_retreat",
    "curiously": "curious_investigative",
    "inquisitively": "curious_investigative",
    "quizzically": "curious_investigative",
    "wearily": "weary_exasperated",
    "tiredly": "weary_exasperated",
    "heavily": "weary_exasperated",
    "exasperated": "weary_exasperated",
    "solemnly": "solemn_reverent",
    "reverently": "solemn_reverent",
    "gravely": "solemn_reverent",
    "slyly": "deceptive_bluff",
    "deceptively": "deceptive_bluff",
    "innocently": "deceptive_bluff",
    "urgently": "tactical_signal",
    "sharply": "tactical_signal",
    "tactically": "tactical_signal",
}


def infer_tone_valence(tone: str | None) -> SemanticValence:
    """Infer structured SemanticValence from a freeform tone or mannerism string."""
    if not tone:
        return "neutral"
    lowered = tone.strip().lower()
    if lowered in TONE_VALENCE_MAP:
        return TONE_VALENCE_MAP[lowered]
    for token in re.findall(r"[a-z]+", lowered):
        if token in TONE_VALENCE_MAP:
            return TONE_VALENCE_MAP[token]
    return "neutral"


def _simple_emote(
    verb: str,
    third_person: str,
    category: EmoteCategory,
    valence: SemanticValence,
    *,
    prep: str = "at",
    aliases: tuple[str, ...] = (),
    no_target_actor_tail: str = "",
    no_target_room_tail: str = "",
) -> EmoteSpec:
    """Build a concise 3-perspective EmoteSpec for regular transitive/intransitive verbs."""
    return EmoteSpec(
        verb=verb,
        aliases=aliases,
        category=category,
        valence=valence,
        no_target_actor=f"You {verb}{no_target_actor_tail}{{adv}}.",
        no_target_room=f"{{actor}} {third_person}{no_target_room_tail}{{adv}}.",
        targeted_actor=f"You {verb}{{adv}} {prep} {{target}}.",
        targeted_target=f"{{actor}} {third_person}{{adv}} {prep} you.",
        targeted_room=f"{{actor}} {third_person}{{adv}} {prep} {{target}}.",
    )


def _custom_phrase(
    verb: str,
    category: EmoteCategory,
    valence: SemanticValence,
    *,
    no_target_actor: str,
    no_target_room: str,
    targeted_actor: str,
    targeted_target: str,
    targeted_room: str,
    aliases: tuple[str, ...] = (),
    audio_clip_ref: str | None = None,
    vfx_cue: str | None = None,
) -> EmoteSpec:
    return EmoteSpec(
        verb=verb,
        aliases=aliases,
        category=category,
        valence=valence,
        no_target_actor=no_target_actor,
        no_target_room=no_target_room,
        targeted_actor=targeted_actor,
        targeted_target=targeted_target,
        targeted_room=targeted_room,
        audio_clip_ref=audio_clip_ref,
        vfx_cue=vfx_cue,
    )


_EMOTE_LIST: tuple[EmoteSpec, ...] = (
    # --- Greetings & Respect (12) ---
    _simple_emote("nod", "nods", "greetings_respect", "respectful_greeting", prep="to"),
    _simple_emote("bow", "bows", "greetings_respect", "respectful_greeting", prep="to"),
    _simple_emote("salute", "salutes", "greetings_respect", "respectful_greeting", prep="to"),
    _simple_emote("curtsey", "curtseys", "greetings_respect", "respectful_greeting", prep="to"),
    _simple_emote("wave", "waves", "greetings_respect", "warm_friendly", prep="to"),
    _custom_phrase(
        "handshake",
        "greetings_respect",
        "respectful_greeting",
        aliases=("shake",),
        no_target_actor="You extend a hand{adv} in formal greeting.",
        no_target_room="{actor} extends a hand{adv} in formal greeting.",
        targeted_actor="You clasp hands{adv} with {target}.",
        targeted_target="{actor} clasps hands{adv} with you.",
        targeted_room="{actor} clasps hands{adv} with {target}.",
    ),
    _simple_emote("kneel", "kneels", "greetings_respect", "solemn_reverent", prep="before"),
    _custom_phrase(
        "toast",
        "greetings_respect",
        "cheerful_celebration",
        no_target_actor="You raise your cup{adv} in a spirited toast.",
        no_target_room="{actor} raises a cup{adv} in a spirited toast.",
        targeted_actor="You raise your cup{adv} in toast to {target}.",
        targeted_target="{actor} raises a cup{adv} in toast to you.",
        targeted_room="{actor} raises a cup{adv} in toast to {target}.",
    ),
    _custom_phrase(
        "hail",
        "greetings_respect",
        "respectful_greeting",
        no_target_actor="You raise an open hand{adv} and call out a hail.",
        no_target_room="{actor} raises an open hand{adv} and calls out a hail.",
        targeted_actor="You hail {target}{adv} with a raised hand.",
        targeted_target="{actor} hails you{adv} with a raised hand.",
        targeted_room="{actor} hails {target}{adv} with a raised hand.",
    ),
    _custom_phrase(
        "welcome",
        "greetings_respect",
        "warm_friendly",
        no_target_actor="You spread your arms{adv} in an open welcome.",
        no_target_room="{actor} spreads both arms{adv} in an open welcome.",
        targeted_actor="You bid {target} welcome{adv}.",
        targeted_target="{actor} bids you welcome{adv}.",
        targeted_room="{actor} bids {target} welcome{adv}.",
    ),
    _custom_phrase(
        "tiphat",
        "greetings_respect",
        "respectful_greeting",
        no_target_actor="You tip your brim{adv} politely.",
        no_target_room="{actor} tips their brim{adv} politely.",
        targeted_actor="You tip your brim{adv} toward {target}.",
        targeted_target="{actor} tips their brim{adv} toward you.",
        targeted_room="{actor} tips their brim{adv} toward {target}.",
    ),
    _custom_phrase(
        "farewell",
        "greetings_respect",
        "warm_friendly",
        aliases=("goodbye",),
        no_target_actor="You incline your head{adv} in parting farewell.",
        no_target_room="{actor} inclines their head{adv} in parting farewell.",
        targeted_actor="You bid {target} a steady farewell{adv}.",
        targeted_target="{actor} bids you a steady farewell{adv}.",
        targeted_room="{actor} bids {target} a steady farewell{adv}.",
    ),
    # --- Emotion & Expression (20) ---
    _simple_emote("smile", "smiles", "emotion_expression", "warm_friendly", prep="at"),
    _simple_emote("grin", "grins", "emotion_expression", "cheerful_celebration", prep="at"),
    _simple_emote("laugh", "laughs", "emotion_expression", "cheerful_celebration", prep="at"),
    _simple_emote("chuckle", "chuckles", "emotion_expression", "warm_friendly", prep="at"),
    _simple_emote("cackle", "cackles", "emotion_expression", "sarcastic_taunt", prep="at"),
    _simple_emote("sigh", "sighs", "emotion_expression", "weary_exasperated", prep="at"),
    _simple_emote("frown", "frowns", "emotion_expression", "weary_exasperated", prep="at"),
    _simple_emote("scowl", "scowls", "emotion_expression", "hostile_intimidation", prep="at"),
    _simple_emote("glare", "glares", "emotion_expression", "hostile_intimidation", prep="at"),
    _simple_emote("wink", "winks", "emotion_expression", "warm_friendly", prep="at"),
    _simple_emote("blush", "blushes", "emotion_expression", "affectionate_comfort", prep="at"),
    _simple_emote("wince", "winces", "emotion_expression", "fearful_retreat", prep="at"),
    _simple_emote("shiver", "shivers", "emotion_expression", "fearful_retreat", prep="at"),
    _simple_emote("groan", "groans", "emotion_expression", "weary_exasperated", prep="at"),
    _simple_emote("cry", "cries", "emotion_expression", "submissive_plea", prep="before"),
    _simple_emote("smirk", "smirks", "emotion_expression", "sarcastic_taunt", prep="at"),
    _simple_emote("gasp", "gasps", "emotion_expression", "curious_investigative", prep="at"),
    _simple_emote("snicker", "snickers", "emotion_expression", "sarcastic_taunt", prep="at"),
    _simple_emote("sob", "sobs", "emotion_expression", "submissive_plea", prep="before"),
    _simple_emote("beam", "beams", "emotion_expression", "cheerful_celebration", prep="at"),
    # --- Body Language & Gestures (17) ---
    _simple_emote("shrug", "shrugs", "body_language", "dismissive_scorn", prep="at"),
    _simple_emote("point", "points", "body_language", "tactical_signal", prep="at"),
    _simple_emote("beckon", "beckons", "body_language", "tactical_signal", prep="to"),
    _simple_emote("clap", "claps", "body_language", "cheerful_celebration", prep="for"),
    _simple_emote("applaud", "applauds", "body_language", "cheerful_celebration", prep="for"),
    _custom_phrase(
        "facepalm",
        "body_language",
        "weary_exasperated",
        no_target_actor="You bury your face in your palm{adv}.",
        no_target_room="{actor} buries their face in one palm{adv}.",
        targeted_actor="You bury your face in your palm{adv} over {target}.",
        targeted_target="{actor} buries their face in one palm{adv} over you.",
        targeted_room="{actor} buries their face in one palm{adv} over {target}.",
    ),
    _custom_phrase(
        "foldarms",
        "body_language",
        "dismissive_scorn",
        aliases=("crossarms",),
        no_target_actor="You fold your arms{adv} across your chest.",
        no_target_room="{actor} folds both arms{adv} across their chest.",
        targeted_actor="You fold your arms{adv} while watching {target}.",
        targeted_target="{actor} folds both arms{adv} while watching you.",
        targeted_room="{actor} folds both arms{adv} while watching {target}.",
    ),
    _custom_phrase(
        "lean",
        "body_language",
        "neutral",
        no_target_actor="You lean back{adv} and take measure of the room.",
        no_target_room="{actor} leans back{adv} and takes measure of the room.",
        targeted_actor="You lean in{adv} toward {target}.",
        targeted_target="{actor} leans in{adv} toward you.",
        targeted_room="{actor} leans in{adv} toward {target}.",
    ),
    _custom_phrase(
        "pace",
        "body_language",
        "weary_exasperated",
        no_target_actor="You pace steadily{adv} across the floor.",
        no_target_room="{actor} paces steadily{adv} across the floor.",
        targeted_actor="You pace restlessly{adv} around {target}.",
        targeted_target="{actor} paces restlessly{adv} around you.",
        targeted_room="{actor} paces restlessly{adv} around {target}.",
    ),
    _custom_phrase(
        "stretch",
        "body_language",
        "neutral",
        no_target_actor="You stretch your shoulders{adv} to loosen stiff joints.",
        no_target_room="{actor} stretches both shoulders{adv} to loosen stiff joints.",
        targeted_actor="You stretch out{adv} near {target}.",
        targeted_target="{actor} stretches out{adv} near you.",
        targeted_room="{actor} stretches out{adv} near {target}.",
    ),
    _simple_emote("yawn", "yawns", "body_language", "dismissive_scorn", prep="at"),
    _simple_emote("stare", "stares", "body_language", "curious_investigative", prep="at"),
    _custom_phrase(
        "ponder",
        "body_language",
        "curious_investigative",
        no_target_actor="You pause to ponder{adv} the puzzle ahead.",
        no_target_room="{actor} pauses to ponder{adv} the puzzle ahead.",
        targeted_actor="You study {target}{adv} in deep thought.",
        targeted_target="{actor} studies you{adv} in deep thought.",
        targeted_room="{actor} studies {target}{adv} in deep thought.",
    ),
    _custom_phrase(
        "strokechin",
        "body_language",
        "curious_investigative",
        no_target_actor="You stroke your chin{adv} thoughtfully.",
        no_target_room="{actor} strokes their chin{adv} thoughtfully.",
        targeted_actor="You stroke your chin{adv} while sizing up {target}.",
        targeted_target="{actor} strokes their chin{adv} while sizing you up.",
        targeted_room="{actor} strokes their chin{adv} while sizing up {target}.",
    ),
    _simple_emote("squint", "squints", "body_language", "curious_investigative", prep="at"),
    _custom_phrase(
        "tapfoot",
        "body_language",
        "weary_exasperated",
        no_target_actor="You tap your boot{adv} impatiently.",
        no_target_room="{actor} taps one boot{adv} impatiently.",
        targeted_actor="You tap your boot{adv} while waiting on {target}.",
        targeted_target="{actor} taps one boot{adv} while waiting on you.",
        targeted_room="{actor} taps one boot{adv} while waiting on {target}.",
    ),
    _custom_phrase(
        "eyebrow",
        "body_language",
        "curious_investigative",
        aliases=("raisebrow",),
        no_target_actor="You arch an eyebrow{adv} in quiet skepticism.",
        no_target_room="{actor} arches an eyebrow{adv} in quiet skepticism.",
        targeted_actor="You arch an eyebrow{adv} at {target}.",
        targeted_target="{actor} arches an eyebrow{adv} at you.",
        targeted_room="{actor} arches an eyebrow{adv} at {target}.",
    ),
    # --- Tactical & Atmospheric (15) ---
    _custom_phrase(
        "taunt",
        "tactical_atmospheric",
        "sarcastic_taunt",
        no_target_actor="You call out a sharp taunt{adv} to the room.",
        no_target_room="{actor} calls out a sharp taunt{adv} to the room.",
        targeted_actor="You taunt {target}{adv} with a biting challenge.",
        targeted_target="{actor} taunts you{adv} with a biting challenge.",
        targeted_room="{actor} taunts {target}{adv} with a biting challenge.",
    ),
    _custom_phrase(
        "threaten",
        "tactical_atmospheric",
        "hostile_intimidation",
        no_target_actor="You shift into a threatening stance{adv}.",
        no_target_room="{actor} shifts into a threatening stance{adv}.",
        targeted_actor="You threaten {target}{adv}, closing your grip.",
        targeted_target="{actor} threatens you{adv} with a cold warning.",
        targeted_room="{actor} threatens {target}{adv} with a cold warning.",
    ),
    _simple_emote("cower", "cowers", "tactical_atmospheric", "fearful_retreat", prep="from"),
    _simple_emote("flinch", "flinches", "tactical_atmospheric", "fearful_retreat", prep="at"),
    _simple_emote("cheer", "cheers", "tactical_atmospheric", "cheerful_celebration", prep="for"),
    _simple_emote("spit", "spits", "tactical_atmospheric", "dismissive_scorn", prep="toward"),
    _custom_phrase(
        "bandage",
        "tactical_atmospheric",
        "affectionate_comfort",
        no_target_actor="You wrap a clean bandage{adv} around your wounds.",
        no_target_room="{actor} wraps a clean bandage{adv} around fresh scrapes.",
        targeted_actor="You tend to {target}{adv} with fresh bandages.",
        targeted_target="{actor} tends to your wounds{adv} with fresh bandages.",
        targeted_room="{actor} tends to {target}{adv} with fresh bandages.",
    ),
    _custom_phrase(
        "inspect",
        "tactical_atmospheric",
        "curious_investigative",
        no_target_actor="You inspect your gear and surroundings{adv}.",
        no_target_room="{actor} inspects the surroundings{adv}.",
        targeted_actor="You inspect {target}{adv} with a practiced eye.",
        targeted_target="{actor} inspects you{adv} with a practiced eye.",
        targeted_room="{actor} inspects {target}{adv} with a practiced eye.",
    ),
    _custom_phrase(
        "warmhands",
        "tactical_atmospheric",
        "affectionate_comfort",
        no_target_actor="You hold your hands out{adv} toward the nearest warmth.",
        no_target_room="{actor} holds both hands out{adv} toward the nearest warmth.",
        targeted_actor="You stand beside {target}{adv}, warming your hands.",
        targeted_target="{actor} stands beside you{adv}, warming cold hands.",
        targeted_room="{actor} stands beside {target}{adv}, warming cold hands.",
    ),
    _custom_phrase(
        "drink",
        "tactical_atmospheric",
        "warm_friendly",
        no_target_actor="You take a measured drink{adv} from your flask.",
        no_target_room="{actor} takes a measured drink{adv} from a flask.",
        targeted_actor="You raise a drink{adv} toward {target} and sip.",
        targeted_target="{actor} raises a drink{adv} toward you and sips.",
        targeted_room="{actor} raises a drink{adv} toward {target} and sips.",
    ),
    _custom_phrase(
        "eat",
        "tactical_atmospheric",
        "neutral",
        no_target_actor="You take a quick bite of rations{adv}.",
        no_target_room="{actor} takes a quick bite of rations{adv}.",
        targeted_actor="You share provisions{adv} alongside {target}.",
        targeted_target="{actor} shares provisions{adv} alongside you.",
        targeted_room="{actor} shares provisions{adv} alongside {target}.",
    ),
    _custom_phrase(
        "saluteblade",
        "tactical_atmospheric",
        "respectful_greeting",
        no_target_actor="You lift your weapon hilt-high{adv} in martial salute.",
        no_target_room="{actor} lifts a weapon hilt-high{adv} in martial salute.",
        targeted_actor="You dip your blade{adv} in formal salute to {target}.",
        targeted_target="{actor} dips a blade{adv} in formal salute to you.",
        targeted_room="{actor} dips a blade{adv} in formal salute to {target}.",
    ),
    _custom_phrase(
        "listen",
        "tactical_atmospheric",
        "curious_investigative",
        no_target_actor="You freeze and listen closely{adv} for distant movement.",
        no_target_room="{actor} freezes and listens closely{adv} for distant movement.",
        targeted_actor="You lean closer{adv}, listening intently to {target}.",
        targeted_target="{actor} leans closer{adv}, listening intently to you.",
        targeted_room="{actor} leans closer{adv}, listening intently to {target}.",
    ),
    _simple_emote(
        "whistle",
        "whistles",
        "tactical_atmospheric",
        "tactical_signal",
        prep="toward",
    ),
    _custom_phrase(
        "hush",
        "tactical_atmospheric",
        "tactical_signal",
        no_target_actor="You raise a finger to your lips{adv}, signaling silence.",
        no_target_room="{actor} raises a finger to their lips{adv}, signaling silence.",
        targeted_actor="You signal {target}{adv} to keep quiet.",
        targeted_target="{actor} signals you{adv} to keep quiet.",
        targeted_room="{actor} signals {target}{adv} to keep quiet.",
    ),
)

BUILTIN_EMOTES: dict[str, EmoteSpec] = {spec.verb: spec for spec in _EMOTE_LIST}
_BUILTIN_ALIAS_MAP: dict[str, str] = {
    alias.lower(): spec.verb for spec in _EMOTE_LIST for alias in spec.aliases
}


def resolve_emote(
    verb: str,
    custom_emotes: Mapping[str, EmoteSpec] | None = None,
) -> EmoteSpec | None:
    """Look up a social emote by canonical verb or alias, preferring custom definitions."""
    key = verb.strip().lower()
    if not key:
        return None
    if custom_emotes:
        if key in custom_emotes:
            return custom_emotes[key]
        for spec in custom_emotes.values():
            if spec.verb.lower() == key or key in {a.lower() for a in spec.aliases}:
                return spec
    if key in BUILTIN_EMOTES:
        return BUILTIN_EMOTES[key]
    canonical = _BUILTIN_ALIAS_MAP.get(key)
    return BUILTIN_EMOTES.get(canonical) if canonical else None


def _render_template(
    template: str,
    *,
    actor_name: str,
    target_name: str,
    adverb: str | None,
) -> str:
    clean_adv = adverb.strip() if adverb else ""
    adv_prefix = f" {clean_adv}" if clean_adv else ""

    has_adv_token = "{adv}" in template or "{adverb}" in template
    rendered = (
        template.replace("{actor}", actor_name)
        .replace("{target}", target_name)
        .replace("{adv}", adv_prefix)
        .replace("{adverb}", clean_adv)
    )
    if clean_adv and not has_adv_token:
        if rendered.endswith((".", "!", "?")):
            rendered = f"{rendered[:-1]} ({clean_adv}){rendered[-1]}"
        else:
            rendered = f"{rendered} ({clean_adv})"
    return _MULTISPACE_RE.sub(" ", rendered).strip()


def _attach_speech(clause: str, speech_verb: str, speech: str | None) -> str:
    if not speech:
        return clause
    clean_speech = speech.strip()
    if not clean_speech:
        return clause
    base = clause[:-1] if clause.endswith(".") else clause
    return f'{base} {speech_verb}, "{clean_speech}"'


def render_emote(
    spec: EmoteSpec,
    actor_name: str,
    *,
    target_name: str | None = None,
    adverb: str | None = None,
    speech: str | None = None,
) -> RenderedPerspectives:
    """Render an EmoteSpec into 3-perspective actor, target, and room views."""
    clean_speech = speech.strip() if speech and speech.strip() else None
    spoken_segments: tuple[str, ...] = (clean_speech,) if clean_speech else ()

    valence = spec.valence
    if adverb:
        adv_valence = infer_tone_valence(adverb)
        if adv_valence != "neutral":
            valence = adv_valence

    if target_name:
        actor_base = _render_template(
            spec.targeted_actor,
            actor_name=actor_name,
            target_name=target_name,
            adverb=adverb,
        )
        target_base = _render_template(
            spec.targeted_target,
            actor_name=actor_name,
            target_name=target_name,
            adverb=adverb,
        )
        room_base = _render_template(
            spec.targeted_room,
            actor_name=actor_name,
            target_name=target_name,
            adverb=adverb,
        )
        return RenderedPerspectives(
            to_actor=_attach_speech(actor_base, spec.speech_verb_actor, clean_speech),
            to_target=_attach_speech(target_base, spec.speech_verb_third, clean_speech),
            to_room=_attach_speech(room_base, spec.speech_verb_third, clean_speech),
            valence=valence,
            spoken_segments=spoken_segments,
            audio_clip_ref=spec.audio_clip_ref,
            vfx_cue=spec.vfx_cue,
        )

    actor_base = _render_template(
        spec.no_target_actor,
        actor_name=actor_name,
        target_name="",
        adverb=adverb,
    )
    room_base = _render_template(
        spec.no_target_room,
        actor_name=actor_name,
        target_name="",
        adverb=adverb,
    )
    return RenderedPerspectives(
        to_actor=_attach_speech(actor_base, spec.speech_verb_actor, clean_speech),
        to_target=None,
        to_room=_attach_speech(room_base, spec.speech_verb_third, clean_speech),
        valence=valence,
        spoken_segments=spoken_segments,
        audio_clip_ref=spec.audio_clip_ref,
        vfx_cue=spec.vfx_cue,
    )


def list_emote_completions(
    prefix: str = "",
    custom_emotes: Mapping[str, EmoteSpec] | None = None,
) -> tuple[str, ...]:
    """Return sorted social emote verbs matching an autocomplete prefix."""
    clean_prefix = prefix.strip().lower().lstrip("/:")
    names: set[str] = set(BUILTIN_EMOTES.keys())
    if custom_emotes:
        for spec in custom_emotes.values():
            names.add(spec.verb.lower())
    return tuple(sorted(name for name in names if name.startswith(clean_prefix)))
