"""Diegetic communication mediums, 3-tier presets, helmet/vacuum physics & couriers."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping, Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.mud_parser.diegetic_languages import (
    LanguageBlock,
    ListenerLanguageProfile,
    filter_message_for_listener,
)

MediumTopology = Literal[
    "tuned_frequency",
    "mental_link",
    "resource_gated_artifact",
    "persistent_network",
    "public_broadcast",
    "async_courier",
]
AudibilityMode = Literal["audible_speech", "subvocal_whisper", "silent_mental_or_text"]
PaProjectionTier = Literal["whisper_amp", "normal", "loud_hailer", "booming_resonance"]
PaTimbreMode = Literal[
    "clean_natural",
    "metallic_vocoder",
    "deep_dreadnought",
    "scrambled_anonymous",
    "voice_mimic",
]
ChannelPresetTier = Literal["canonical_ruleset", "shared_party", "personal_contact"]


def _norm_tags(tags: Sequence[str]) -> set[str]:
    return {t.strip().lstrip("#").lower() for t in tags if t.strip()}


class VoiceModulatorProfile(BaseModel):
    """Optional fine-grained external PA & vocal filtering configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    projection: PaProjectionTier = "normal"
    timbre: PaTimbreMode = "clean_natural"
    mimic_target_id: str | None = None
    mimic_target_name: str | None = None


class CommunicationMediumBlock(BaseModel):
    """Ruleset/world-defined communication medium across 6 universal topologies."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    medium_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    topology: MediumTopology
    mud_verbs: tuple[str, ...] = ()
    audibility_mode: AudibilityMode = "audible_speech"
    requires_vocal_speech: bool = True
    requires_somatic_input: bool = False
    requires_mental_action: bool = False
    required_capability_tag: str | None = None
    suppress_tags: tuple[str, ...] = ()
    max_words: int | None = Field(default=None, ge=1)
    cross_plane_failure_pct: int = Field(default=0, ge=0, le=100)
    telepathic_comprehension_mode: Literal["language_dependent", "universal_conceptual"] = (
        "language_dependent"
    )
    default_signal_quality: float = Field(default=1.0, ge=0.0, le=1.0)
    travel_turns_per_hop: int = Field(default=1, ge=0)
    resource_cost_pool: str | None = None
    resource_cost_amount: int = Field(default=0, ge=0)


class ChannelPreset(BaseModel):
    """Friendly alias or location-aware station entry in ChannelPresetRegistry."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    preset_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    frequency_or_address: str = Field(min_length=1)
    aliases: tuple[str, ...] = ()
    semantic_tags: tuple[str, ...] = ()
    location_scope: str | None = None
    tier: ChannelPresetTier = "canonical_ruleset"
    is_encrypted: bool = False


class ChannelPresetRegistry(BaseModel):
    """Three-tier channel & frequency alias registry (Ruleset, Shared Party, Personal)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    presets: dict[str, ChannelPreset] = Field(default_factory=dict)

    def save_preset(self, preset: ChannelPreset) -> ChannelPresetRegistry:
        """Return a new registry with preset added or updated cleanly."""
        next_map = dict(self.presets)
        next_map[preset.preset_id] = preset
        return ChannelPresetRegistry(presets=next_map)

    def resolve(
        self,
        alias_or_frequency: str,
        *,
        location_id: str | None = None,
    ) -> ChannelPreset | None:
        """Resolve an alias, semantic tag (#local-news), or raw frequency deterministically."""
        query = alias_or_frequency.strip().lower()
        query_norm = query.lstrip("#")
        if not query:
            return None

        # 1. Location-scoped semantic tags / aliases take highest precedence when in location_id
        if location_id is not None:
            loc_norm = location_id.strip().lower()
            for preset in self.presets.values():
                if preset.location_scope and preset.location_scope.lower() == loc_norm:
                    aliases_norm = {a.lstrip("#").lower() for a in preset.aliases}
                    sem_norm = {s.lstrip("#").lower() for s in preset.semantic_tags}
                    if (
                        query_norm in aliases_norm
                        or query_norm in sem_norm
                        or query == preset.frequency_or_address.lower()
                    ):
                        return preset

        # 2. Global exact preset_id, alias, semantic tag, or raw frequency
        for preset in self.presets.values():
            aliases_norm = {a.lstrip("#").lower() for a in preset.aliases}
            sem_norm = {s.lstrip("#").lower() for s in preset.semantic_tags}
            if (
                query == preset.preset_id.lower()
                or query == preset.frequency_or_address.lower()
                or query_norm in aliases_norm
                or query_norm in sem_norm
            ):
                return preset

        return None


class SpeakerAcousticState(BaseModel):
    """Speaker environmental, equipment, and condition state for comms gating."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    entity_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    room_id: str = Field(min_length=1)
    z_stratum: int = 0
    dimension_phase: str = "material"
    conditions: tuple[str, ...] = ()
    capability_tags: tuple[str, ...] = ()
    room_environment_tags: tuple[str, ...] = ()
    external_pa_enabled: bool = False
    voice_modulator: VoiceModulatorProfile = Field(default_factory=VoiceModulatorProfile)
    channel_handle: str | None = None


class ListenerAcousticState(BaseModel):
    """Receiving seat acoustic, tuning, and language state."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    seat_id: str = Field(min_length=1)
    entity_id: str = Field(min_length=1)
    room_id: str = Field(min_length=1)
    dimension_phase: str = "material"
    z_stratum: int = 0
    conditions: tuple[str, ...] = ()
    capability_tags: tuple[str, ...] = ()
    room_environment_tags: tuple[str, ...] = ()
    tuned_channel: str | None = None
    has_receiver_prop: bool = False
    can_lip_read: bool = False
    language_profile: ListenerLanguageProfile


class InTransitMessage(BaseModel):
    """Asynchronous physical courier dispatch tracked against campaign turn/time clocks."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    message_id: str
    sender_id: str
    recipient_id: str
    origin_node: str
    dest_node: str
    hops: int
    eta_turns: int
    plaintext: str
    language_id: str | None = None
    attached_items: tuple[str, ...] = ()


class TransmissionDelivery(BaseModel):
    """Delivered wire payload for one seat after acoustic & fluency gating."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    seat_id: str
    entity_id: str
    rendered_text: str
    heard_audibly: bool = False
    received_via_medium: bool = False
    lip_read_partial: bool = False
    language_tier: str = "fluent"
    decoded_cant_subtext: str | None = None


class CommTransmissionResult(BaseModel):
    """Complete deterministic outcome of evaluating a communication transmission."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    delivered: bool
    blocked_reason: str | None = None
    muffled_struggle_notice: str | None = None
    room_bleed_count: int = 0
    room_bleed_hops: int = 0
    breaks_stealth: bool = False
    signal_quality: float = 1.0
    resolved_channel: ChannelPreset | None = None
    deliveries: tuple[TransmissionDelivery, ...] = ()
    in_transit: InTransitMessage | None = None
    planar_misfire: bool = False


def degrade_signal_text(text: str, signal_quality: float, seed_key: str) -> str:
    """Deterministically attenuate text with static crackle when signal_quality < 0.7."""
    if signal_quality >= 0.7 or not text.strip():
        return text

    drop_pct = min(65, max(15, int((0.75 - signal_quality) * 90)))
    words = text.split()
    corrupted: list[str] = []
    for idx, word in enumerate(words):
        digest = hashlib.sha256(f"{seed_key}:{idx}:{word}".encode()).digest()
        if len(word) >= 3 and (digest[0] % 100) < drop_pct:
            cut = max(1, len(word) // 2)
            corrupted.append(f"{word[:cut]}--")
        else:
            corrupted.append(word)
    return f'[...crackle...] "{" ".join(corrupted)}"'


def evaluate_speech_gating(
    speaker: SpeakerAcousticState,
    *,
    medium: CommunicationMediumBlock | None = None,
    special_mode: Literal["local_say", "touch_helmet", "sign"] | None = None,
) -> tuple[bool, str | None, str | None]:
    """Check vocal, somatic, mental, helmet, vacuum, silence, and suppress_tag gates."""
    conds = _norm_tags(speaker.conditions)
    env = _norm_tags(speaker.room_environment_tags)
    caps = _norm_tags(speaker.capability_tags)

    has_sealed_helmet = "sealed_helmet" in conds or "sealed_helmet" in caps
    has_hydro_vox = "hydro_vox" in caps or has_sealed_helmet

    if special_mode == "sign":
        req_vocal, req_somatic, req_mental = False, True, False
    elif special_mode == "touch_helmet":
        req_vocal, req_somatic, req_mental = True, True, False
    elif medium is not None:
        req_vocal = medium.requires_vocal_speech
        req_somatic = medium.requires_somatic_input
        req_mental = medium.requires_mental_action
    else:
        req_vocal, req_somatic, req_mental = True, False, False

    if "unconscious" in conds or "mind_stunned" in conds:
        return False, "unconscious_or_mind_stunned", None

    if conds & {"paralyzed", "petrified", "stasis_locked"}:
        if req_mental and not req_vocal and not req_somatic:
            pass
        else:
            return False, "immobilized_blocks_vocal_and_somatic", None

    if conds & {"muted", "gagged", "silenced", "suffocating"} and req_vocal:
        notice = (
            f"{speaker.name} makes an urgent, muffled sound behind the gag!"
            if "gagged" in conds
            else None
        )
        return False, "vocal_condition_blocked", notice

    if "magical_silence" in env and req_vocal:
        return False, "magical_silence_blocks_acoustic_speech", None

    if "vacuum" in env:
        if special_mode == "touch_helmet":
            if not has_sealed_helmet:
                return False, "touch_helmet_requires_sealed_helmet", None
        elif special_mode == "sign":
            pass
        elif medium is not None:
            if req_vocal and not has_sealed_helmet:
                return False, "vacuum_no_air_without_sealed_helmet", None
        else:
            return (
                False,
                "vacuum_no_air",
                (
                    "There is no air to carry sound in a vacuum; use your suit radio "
                    "or touch-helmet / hand signals."
                ),
            )

    if "underwater" in env and req_vocal and not has_hydro_vox and special_mode != "sign":
        return (
            False,
            "underwater_requires_sealed_helmet",
            f"{speaker.name} lets out a muffled burst of rising bubbles.",
        )

    if medium is not None:
        if (
            medium.required_capability_tag
            and medium.required_capability_tag.lstrip("#").lower() not in caps
        ):
            return False, f"missing_capability:{medium.required_capability_tag}", None
        for suppress in medium.suppress_tags:
            s_norm = suppress.lstrip("#").lower()
            if s_norm in env or s_norm in conds:
                return False, f"suppressed_by:{suppress}", None

    return True, None, None


def _display_speaker_for_pa(speaker: SpeakerAcousticState, *, external: bool) -> str:
    if not external:
        return speaker.name
    profile = speaker.voice_modulator
    if profile.timbre == "scrambled_anonymous":
        return "[[entity:scrambled_voice|An Electronically Scrambled Voice]]"
    if profile.timbre == "voice_mimic" and profile.mimic_target_name:
        return profile.mimic_target_name
    return speaker.name


def resolve_diegetic_transmission(
    speaker: SpeakerAcousticState,
    plaintext: str,
    listeners: Sequence[ListenerAcousticState],
    *,
    medium: CommunicationMediumBlock | None = None,
    special_mode: Literal["local_say", "touch_helmet", "sign"] | None = None,
    target_entity_id: str | None = None,
    channel_query: str | None = None,
    registry: ChannelPresetRegistry | None = None,
    speaker_location_id: str | None = None,
    language: LanguageBlock | None = None,
    all_languages: Mapping[str, LanguageBlock] | None = None,
    cant_subtext: str | None = None,
    d100_roll_fn: Callable[[], int] | None = None,
    courier_dest_node: str | None = None,
    courier_hops: int = 1,
    attached_items: Sequence[str] = (),
) -> CommTransmissionResult:
    """Resolve diegetic comms gating, signal quality, helmet isolation, PA & fluency."""
    allowed, blocked_reason, struggle_notice = evaluate_speech_gating(
        speaker,
        medium=medium,
        special_mode=special_mode,
    )
    if not allowed:
        return CommTransmissionResult(
            delivered=False,
            blocked_reason=blocked_reason,
            muffled_struggle_notice=struggle_notice,
            signal_quality=0.0,
        )

    speaker_conds = _norm_tags(speaker.conditions)
    speaker_caps = _norm_tags(speaker.capability_tags)
    speaker_env = _norm_tags(speaker.room_environment_tags)
    has_sealed_helmet = "sealed_helmet" in speaker_conds or "sealed_helmet" in speaker_caps

    # Word limit enforcement (e.g. max_words: 25)
    if medium is not None and medium.max_words is not None:
        word_count = len(plaintext.split())
        if word_count > medium.max_words:
            return CommTransmissionResult(
                delivered=False,
                blocked_reason=f"exceeds_max_words:{word_count}/{medium.max_words}",
            )

    # Planar failure roll for cross-plane resource-gated transmissions
    if medium is not None and medium.cross_plane_failure_pct > 0:
        cross_plane = any(
            lst.dimension_phase != speaker.dimension_phase
            for lst in listeners
            if target_entity_id is None or lst.entity_id == target_entity_id
        )
        if cross_plane:
            if d100_roll_fn is not None:
                roll_val = d100_roll_fn()
            else:
                digest = hashlib.sha256(f"planar:{speaker.entity_id}:{plaintext}".encode()).digest()
                roll_val = (int.from_bytes(digest[:2], "big") % 100) + 1
            if roll_val <= medium.cross_plane_failure_pct:
                return CommTransmissionResult(
                    delivered=False,
                    blocked_reason="planar_transmission_failed",
                    planar_misfire=True,
                )

    # Resolve ChannelPresetRegistry for frequency / broadcast aliases
    resolved_preset: ChannelPreset | None = None
    if registry is not None and channel_query:
        resolved_preset = registry.resolve(channel_query, location_id=speaker_location_id)

    # Asynchronous physical courier dispatch
    if medium is not None and medium.topology == "async_courier":
        hops = max(1, courier_hops)
        msg_digest = hashlib.sha256(
            f"courier:{speaker.entity_id}:{target_entity_id}:{plaintext}".encode()
        ).hexdigest()[:12]
        dispatch = InTransitMessage(
            message_id=f"msg_{msg_digest}",
            sender_id=speaker.entity_id,
            recipient_id=target_entity_id or "",
            origin_node=speaker.room_id,
            dest_node=courier_dest_node or speaker.room_id,
            hops=hops,
            eta_turns=hops * max(1, medium.travel_turns_per_hop),
            plaintext=plaintext,
            language_id=language.language_id if language else None,
            attached_items=tuple(attached_items),
        )
        return CommTransmissionResult(
            delivered=True,
            breaks_stealth=False,
            signal_quality=1.0,
            resolved_channel=resolved_preset,
            in_transit=dispatch,
        )

    # Signal quality for tuned_frequency (Z-stratum & ion_storm degradation)
    signal_quality = medium.default_signal_quality if medium is not None else 1.0
    if medium is not None and medium.topology == "tuned_frequency":
        if speaker.z_stratum <= -2:
            signal_quality -= 0.25 * (abs(speaker.z_stratum) - 1)
        if "ion_storm" in speaker_env:
            signal_quality -= 0.40
        signal_quality = max(0.15, min(1.0, signal_quality))

    payload_text = degrade_signal_text(
        plaintext, signal_quality, f"{speaker.entity_id}:{speaker.room_id}"
    )

    # Physical room bleed, stealth impact & PA voice modulation
    audibility: AudibilityMode = (
        medium.audibility_mode
        if medium is not None
        else ("silent_mental_or_text" if special_mode == "sign" else "audible_speech")
    )
    pa_profile = speaker.voice_modulator
    external_audible = False
    room_bleed_hops = 0

    if (
        "vacuum" in speaker_env
        or "magical_silence" in speaker_env
        or special_mode in {"touch_helmet", "sign"}
    ):
        external_audible = False
    elif medium is not None:
        if has_sealed_helmet:
            external_audible = speaker.external_pa_enabled
            if external_audible and pa_profile.projection in {"loud_hailer", "booming_resonance"}:
                room_bleed_hops = 2
        else:
            external_audible = audibility == "audible_speech"
    else:
        external_audible = True
        if speaker.external_pa_enabled and pa_profile.projection in {
            "loud_hailer",
            "booming_resonance",
        }:
            room_bleed_hops = 2

    breaks_stealth = external_audible or (medium is None and special_mode != "sign")
    if has_sealed_helmet and not speaker.external_pa_enabled and medium is not None:
        breaks_stealth = False

    universal_conceptual = (
        medium is not None
        and medium.topology == "mental_link"
        and medium.telepathic_comprehension_mode == "universal_conceptual"
    )

    display_speaker_internal = (
        speaker.channel_handle
        if (
            medium is not None
            and medium.topology == "persistent_network"
            and speaker.channel_handle
        )
        else speaker.name
    )
    display_speaker_external = _display_speaker_for_pa(
        speaker, external=speaker.external_pa_enabled or pa_profile.timbre != "clean_natural"
    )

    deliveries: list[TransmissionDelivery] = []
    room_bleed_count = 0

    for listener in listeners:
        listener_conds = _norm_tags(listener.conditions)
        listener_env = _norm_tags(listener.room_environment_tags)
        in_same_room = listener.room_id == speaker.room_id
        is_self = listener.entity_id == speaker.entity_id

        # Check listener suppression for mental links
        if (
            medium is not None
            and medium.suppress_tags
            and (_norm_tags(medium.suppress_tags) & (listener_conds | listener_env))
        ):
            continue

        receives_via_medium = False
        if medium is not None:
            if medium.topology == "tuned_frequency":
                if is_self:
                    receives_via_medium = True
                elif resolved_preset is not None:
                    aliases_and_freq = {
                        resolved_preset.preset_id.lower(),
                        resolved_preset.frequency_or_address.lower(),
                        *(a.lstrip("#").lower() for a in resolved_preset.aliases),
                    }
                    if (
                        listener.tuned_channel
                        and listener.tuned_channel.lstrip("#").lower() in aliases_and_freq
                    ):
                        receives_via_medium = True
                elif channel_query and listener.tuned_channel:
                    receives_via_medium = (
                        listener.tuned_channel.lstrip("#").lower()
                        == channel_query.lstrip("#").lower()
                    )
            elif medium.topology in {"mental_link", "resource_gated_artifact"}:
                receives_via_medium = is_self or (
                    target_entity_id is None or listener.entity_id == target_entity_id
                )
            elif medium.topology == "persistent_network":
                receives_via_medium = (
                    is_self
                    or not channel_query
                    or (
                        listener.tuned_channel is not None
                        and listener.tuned_channel.lstrip("#").lower()
                        == channel_query.lstrip("#").lower()
                    )
                )
            elif medium.topology == "public_broadcast":
                receives_via_medium = (
                    is_self
                    or listener.has_receiver_prop
                    or (
                        resolved_preset is not None
                        and listener.tuned_channel is not None
                        and listener.tuned_channel.lstrip("#").lower()
                        in {
                            resolved_preset.preset_id.lower(),
                            *(a.lstrip("#").lower() for a in resolved_preset.aliases),
                        }
                    )
                )

        heard_audibly = external_audible and in_same_room and not is_self
        if special_mode == "touch_helmet" and listener.entity_id in {
            speaker.entity_id,
            target_entity_id,
        }:
            receives_via_medium = True
        if special_mode == "sign" and in_same_room:
            receives_via_medium = True

        if not receives_via_medium and not heard_audibly:
            continue

        if heard_audibly:
            room_bleed_count += 1

        # #deafened applies strictly to audible channels (never blocks text, mental, or sign)
        is_audio_only = (audibility == "audible_speech" and special_mode not in {"sign"}) and not (
            medium is not None and medium.topology in {"persistent_network", "mental_link"}
        )
        if "deafened" in listener_conds and is_audio_only and not is_self:
            speaker_lbl = display_speaker_external if heard_audibly else display_speaker_internal
            if listener.can_lip_read and in_same_room:
                deliveries.append(
                    TransmissionDelivery(
                        seat_id=listener.seat_id,
                        entity_id=listener.entity_id,
                        rendered_text=(
                            f'You watch {speaker_lbl}\'s lips move [Lip-Reading], "{payload_text}"'
                        ),
                        heard_audibly=False,
                        received_via_medium=receives_via_medium,
                        lip_read_partial=True,
                        language_tier="partial",
                    )
                )
            else:
                deliveries.append(
                    TransmissionDelivery(
                        seat_id=listener.seat_id,
                        entity_id=listener.entity_id,
                        rendered_text=(f"You see {speaker_lbl}'s lips moving, but hear nothing."),
                        heard_audibly=False,
                        received_via_medium=False,
                        language_tier="none",
                    )
                )
            continue

        speaker_name_used = (
            display_speaker_external
            if (heard_audibly or (speaker.external_pa_enabled and external_audible))
            else display_speaker_internal
        )
        prefix = ""
        if resolved_preset is not None and medium is not None:
            chan_lbl = resolved_preset.label
            chan_addr = resolved_preset.frequency_or_address
            prefix = f"[{medium.label} • {chan_lbl} ({chan_addr})] "
        elif medium is not None and medium.topology != "public_broadcast":
            prefix = f"[{medium.label}] "
        elif special_mode == "touch_helmet":
            prefix = "[Helmet Contact] "
        elif special_mode == "sign":
            prefix = "[Hand-Sign] "

        filtered = filter_message_for_listener(
            speaker_name_used,
            payload_text,
            language,
            listener.language_profile,
            all_languages=all_languages,
            cant_subtext=cant_subtext,
            universal_conceptual=universal_conceptual,
        )
        deliveries.append(
            TransmissionDelivery(
                seat_id=listener.seat_id,
                entity_id=listener.entity_id,
                rendered_text=f"{prefix}{filtered.rendered_text}",
                heard_audibly=heard_audibly,
                received_via_medium=receives_via_medium,
                language_tier=filtered.fluency_tier,
                decoded_cant_subtext=filtered.decoded_cant_subtext,
            )
        )

    return CommTransmissionResult(
        delivered=True,
        room_bleed_count=room_bleed_count,
        room_bleed_hops=room_bleed_hops,
        breaks_stealth=breaks_stealth,
        signal_quality=signal_quality,
        resolved_channel=resolved_preset,
        deliveries=tuple(deliveries),
    )
