"""Ruleset-grounded diegetic languages, dialects, written scripts & secret cants."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

FluencyTier = Literal["fluent", "partial", "none"]

_WORD_SPAN_RE = re.compile(r"[A-Za-z0-9']+|[.,!?;:\-]+|\s+")
_SHORT_COMMON_WORDS: frozenset[str] = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "at",
        "be",
        "by",
        "for",
        "from",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "the",
        "to",
        "we",
    }
)


class LanguageBlock(BaseModel):
    """Declarative diegetic language, dialect family, script, or secret cant."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    language_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    family_group: str = ""
    script_alphabet: str = ""
    is_secret_cant: bool = False
    phonetic_syllables: tuple[str, ...] = (
        "kal",
        "eth",
        "vor",
        "sin",
        "dar",
        "tel",
        "mal",
        "ren",
    )
    flavor_adjective: str = "unfamiliar"


class ListenerLanguageProfile(BaseModel):
    """Per-seat language fluency & cipher display preferences for wire scrubbing."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    seat_id: str = Field(min_length=1)
    entity_id: str = Field(min_length=1)
    fluent_languages: tuple[str, ...] = ()
    partial_languages: tuple[str, ...] = ()
    has_universal_translator: bool = False
    knows_cants: tuple[str, ...] = ()
    cipher_display_mode: Literal["phonetic_cipher", "narrative_summary"] = "phonetic_cipher"


class FilteredLanguageMessage(BaseModel):
    """Seat-specific language-filtered output guaranteeing wire plaintext scrubbing."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    seat_id: str
    fluency_tier: FluencyTier
    language_id: str | None = None
    rendered_text: str
    decoded_cant_subtext: str | None = None
    partial_comprehension: bool = False
    plaintext_scrubbed: bool = False


def _syllable_token(word: str, language: LanguageBlock, separator: str = "'") -> str:
    syllables = language.phonetic_syllables or ("kal", "vor", "tel", "ren")
    digest = hashlib.sha256(f"{language.language_id}:{word.lower()}".encode()).digest()
    syl_count = 2 if len(word) <= 6 else 3
    picked = [syllables[digest[idx] % len(syllables)] for idx in range(syl_count)]
    candidate = separator.join(picked)
    if candidate.lower() == word.lower():
        alt = syllables[(digest[0] + 1) % len(syllables)]
        candidate = f"{alt}{separator}{picked[-1]}"
    if word[0].isupper():
        candidate = candidate[0].upper() + candidate[1:]
    return candidate


def generate_phonetic_cipher(plaintext: str, language: LanguageBlock) -> str:
    """Deterministically transform plaintext into phonetic syllables via SHA-256."""
    if not plaintext:
        return ""
    tokens = _WORD_SPAN_RE.findall(plaintext)
    if not tokens:
        return _syllable_token(plaintext, language)

    out: list[str] = []
    for tok in tokens:
        if tok[0].isalnum():
            out.append(_syllable_token(tok, language, separator="'"))
        else:
            out.append(tok)
    return "".join(out)


def mask_partial_comprehension(plaintext: str, language: LanguageBlock) -> str:
    """Preserve root/short words while masking unfamiliar terms into bracketed syllables."""
    if not plaintext:
        return ""
    tokens = _WORD_SPAN_RE.findall(plaintext)
    long_word_indices = [
        idx
        for idx, tok in enumerate(tokens)
        if tok[0].isalnum() and len(tok) >= 4 and tok.lower() not in _SHORT_COMMON_WORDS
    ]
    masked_indices: set[int] = set()
    for idx in long_word_indices:
        digest = hashlib.sha256(
            f"partial:{language.language_id}:{tokens[idx].lower()}:{idx}".encode()
        ).digest()
        if digest[0] % 100 < 45:
            masked_indices.add(idx)

    if long_word_indices and not masked_indices:
        masked_indices.add(long_word_indices[-1])

    out: list[str] = []
    for idx, tok in enumerate(tokens):
        if idx in masked_indices:
            out.append(f"[{_syllable_token(tok, language, separator='-')}]")
        else:
            out.append(tok)
    return "".join(out)


def determine_listener_fluency(
    listener: ListenerLanguageProfile,
    language: LanguageBlock,
    all_languages: Mapping[str, LanguageBlock] | None = None,
) -> FluencyTier:
    """Compute a listener's fluency tier for a spoken/written LanguageBlock."""
    if listener.has_universal_translator:
        return "fluent"
    if language.language_id in listener.fluent_languages:
        return "fluent"
    if language.language_id in listener.partial_languages:
        return "partial"

    family = language.family_group.strip()
    if family and all_languages:
        known_ids = set(listener.fluent_languages) | set(listener.partial_languages)
        for known_id in known_ids:
            known_block = all_languages.get(known_id)
            if known_block is not None and known_block.family_group.strip() == family:
                return "partial"
    return "none"


def filter_message_for_listener(
    speaker_name: str,
    plaintext: str,
    language: LanguageBlock | None,
    listener: ListenerLanguageProfile,
    *,
    all_languages: Mapping[str, LanguageBlock] | None = None,
    cant_subtext: str | None = None,
    universal_conceptual: bool = False,
    speech_verb: str = "says",
) -> FilteredLanguageMessage:
    """Filter dialogue per seat, ensuring non-speakers never receive raw plaintext over wire."""
    if language is None or universal_conceptual:
        rendered = f'{speaker_name} {speech_verb}, "{plaintext}"'
        return FilteredLanguageMessage(
            seat_id=listener.seat_id,
            fluency_tier="fluent",
            language_id=language.language_id if language is not None else None,
            rendered_text=rendered,
            decoded_cant_subtext=cant_subtext if universal_conceptual else None,
            partial_comprehension=False,
            plaintext_scrubbed=False,
        )

    if language.is_secret_cant:
        is_initiate = (
            listener.has_universal_translator
            or language.language_id in listener.knows_cants
            or language.language_id in listener.fluent_languages
        )
        if is_initiate and cant_subtext:
            rendered = (
                f'{speaker_name} {speech_verb}, "{plaintext}" [{language.label}: "{cant_subtext}"]'
            )
            return FilteredLanguageMessage(
                seat_id=listener.seat_id,
                fluency_tier="fluent",
                language_id=language.language_id,
                rendered_text=rendered,
                decoded_cant_subtext=cant_subtext,
                partial_comprehension=False,
                plaintext_scrubbed=False,
            )
        rendered = f'{speaker_name} {speech_verb}, "{plaintext}"'
        return FilteredLanguageMessage(
            seat_id=listener.seat_id,
            fluency_tier="fluent" if is_initiate else "none",
            language_id=language.language_id,
            rendered_text=rendered,
            decoded_cant_subtext=None,
            partial_comprehension=False,
            plaintext_scrubbed=bool(cant_subtext and not is_initiate),
        )

    tier = determine_listener_fluency(listener, language, all_languages)
    if tier == "fluent":
        return FilteredLanguageMessage(
            seat_id=listener.seat_id,
            fluency_tier="fluent",
            language_id=language.language_id,
            rendered_text=f'{speaker_name} {speech_verb} in {language.label}, "{plaintext}"',
            partial_comprehension=False,
            plaintext_scrubbed=False,
        )

    if tier == "partial":
        masked = mask_partial_comprehension(plaintext, language)
        return FilteredLanguageMessage(
            seat_id=listener.seat_id,
            fluency_tier="partial",
            language_id=language.language_id,
            rendered_text=(
                f"{speaker_name} {speech_verb} in {language.label} "
                f'[Partial Comprehension], "{masked}"'
            ),
            partial_comprehension=True,
            plaintext_scrubbed=True,
        )

    if listener.cipher_display_mode == "narrative_summary":
        rendered = (
            f"{speaker_name} {speech_verb} something in a "
            f"{language.flavor_adjective}, unfamiliar tongue."
        )
    else:
        cipher = generate_phonetic_cipher(plaintext, language)
        rendered = (
            f'{speaker_name} speaks in {language.flavor_adjective} {language.label}, "{cipher}"'
        )

    return FilteredLanguageMessage(
        seat_id=listener.seat_id,
        fluency_tier="none",
        language_id=language.language_id,
        rendered_text=rendered,
        partial_comprehension=False,
        plaintext_scrubbed=True,
    )
