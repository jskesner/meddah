"""Unit tests for Diegetic Languages, 6 Comms Topologies & Acoustic/Helmet Physics."""

from __future__ import annotations

import pytest

from app.mud_parser import (
    ChannelPreset,
    ChannelPresetRegistry,
    CommunicationMediumBlock,
    LanguageBlock,
    ListenerAcousticState,
    ListenerLanguageProfile,
    SpeakerAcousticState,
    VoiceModulatorProfile,
    filter_message_for_listener,
    resolve_diegetic_transmission,
)


def _sample_languages() -> dict[str, LanguageBlock]:
    return {
        "elvish": LanguageBlock(
            language_id="elvish",
            label="High Elven",
            family_group="elven_family",
            script_alphabet="Seldarin Runes",
            phonetic_syllables=("ael", "sil", "var", "dorei", "lin", "thas"),
            flavor_adjective="melodic",
        ),
        "wood_elvish": LanguageBlock(
            language_id="wood_elvish",
            label="Wood Elven",
            family_group="elven_family",
            script_alphabet="Leaf Script",
            phonetic_syllables=("syl", "veth", "lor", "nen", "ar", "fen"),
            flavor_adjective="lilting",
        ),
        "thieves_cant": LanguageBlock(
            language_id="thieves_cant",
            label="Thieves' Cant",
            is_secret_cant=True,
            flavor_adjective="innocuous",
        ),
    }


@pytest.mark.zero_ai
def test_language_three_tier_wire_scrubbing_and_secret_cants() -> None:
    """Verify fluent, shared-dialect partial, non-speaker cipher scrubbing & dual cant."""
    langs = _sample_languages()
    plaintext = "The merchant scales are completely rigged"

    fluent_seat = ListenerLanguageProfile(
        seat_id="seat_fluent",
        entity_id="pc_1",
        fluent_languages=("elvish",),
    )
    dialect_seat = ListenerLanguageProfile(
        seat_id="seat_dialect",
        entity_id="pc_2",
        fluent_languages=("wood_elvish",),
    )
    outsider_seat = ListenerLanguageProfile(
        seat_id="seat_outsider",
        entity_id="pc_3",
        cipher_display_mode="phonetic_cipher",
    )
    summary_seat = ListenerLanguageProfile(
        seat_id="seat_summary",
        entity_id="pc_4",
        cipher_display_mode="narrative_summary",
    )
    translator_seat = ListenerLanguageProfile(
        seat_id="seat_trans",
        entity_id="pc_5",
        has_universal_translator=True,
    )

    out_fluent = filter_message_for_listener(
        "Kale", plaintext, langs["elvish"], fluent_seat, all_languages=langs
    )
    assert out_fluent.fluency_tier == "fluent"
    assert plaintext in out_fluent.rendered_text
    assert out_fluent.plaintext_scrubbed is False

    out_dialect = filter_message_for_listener(
        "Kale", plaintext, langs["elvish"], dialect_seat, all_languages=langs
    )
    assert out_dialect.fluency_tier == "partial"
    assert out_dialect.partial_comprehension is True
    assert "Partial Comprehension" in out_dialect.rendered_text
    assert out_dialect.plaintext_scrubbed is True

    out_outsider = filter_message_for_listener(
        "Kale", plaintext, langs["elvish"], outsider_seat, all_languages=langs
    )
    assert out_outsider.fluency_tier == "none"
    assert out_outsider.plaintext_scrubbed is True
    assert "merchant" not in out_outsider.rendered_text.lower()
    assert "rigged" not in out_outsider.rendered_text.lower()

    out_summary = filter_message_for_listener(
        "Kale", plaintext, langs["elvish"], summary_seat, all_languages=langs
    )
    assert "unfamiliar tongue" in out_summary.rendered_text
    assert "merchant" not in out_summary.rendered_text.lower()

    out_trans = filter_message_for_listener(
        "Kale", plaintext, langs["elvish"], translator_seat, all_languages=langs
    )
    assert out_trans.fluency_tier == "fluent"
    assert plaintext in out_trans.rendered_text

    # Secret cant: initiates see decoded subtext, outsiders get stripped wire payload
    cant_initiate = ListenerLanguageProfile(
        seat_id="s_rogue", entity_id="pc_rogue", knows_cants=("thieves_cant",)
    )
    res_init = filter_message_for_listener(
        "Kale",
        "Lovely weather for a harvest",
        langs["thieves_cant"],
        cant_initiate,
        cant_subtext="Ambush at the east gate at dusk",
    )
    res_other = filter_message_for_listener(
        "Kale",
        "Lovely weather for a harvest",
        langs["thieves_cant"],
        outsider_seat,
        cant_subtext="Ambush at the east gate at dusk",
    )
    assert res_init.decoded_cant_subtext == "Ambush at the east gate at dusk"
    assert "Ambush" in res_init.rendered_text
    assert res_other.decoded_cant_subtext is None
    assert "Ambush" not in res_other.rendered_text
    assert "Lovely weather for a harvest" in res_other.rendered_text


@pytest.mark.zero_ai
def test_all_six_comms_topologies_and_channel_registry() -> None:
    """Exercise tuned_frequency, mental_link, artifact, network, broadcast & courier."""
    radio_med = CommunicationMediumBlock(
        medium_id="suit_radio",
        label="Radio",
        topology="tuned_frequency",
        mud_verbs=("radio",),
        audibility_mode="audible_speech",
        requires_vocal_speech=True,
        required_capability_tag="handheld_radio",
    )
    telepathy_med = CommunicationMediumBlock(
        medium_id="mind_link",
        label="Telepathy",
        topology="mental_link",
        mud_verbs=("telepathy",),
        audibility_mode="silent_mental_or_text",
        requires_vocal_speech=False,
        requires_somatic_input=False,
        requires_mental_action=True,
        telepathic_comprehension_mode="universal_conceptual",
        suppress_tags=("anti_psionic",),
    )
    sending_med = CommunicationMediumBlock(
        medium_id="sending_spell",
        label="Sending",
        topology="resource_gated_artifact",
        audibility_mode="subvocal_whisper",
        max_words=25,
        cross_plane_failure_pct=5,
    )
    bbs_med = CommunicationMediumBlock(
        medium_id="matrix_bbs",
        label="Matrix BBS",
        topology="persistent_network",
        audibility_mode="silent_mental_or_text",
        requires_vocal_speech=False,
        requires_somatic_input=True,
    )
    broadcast_med = CommunicationMediumBlock(
        medium_id="holo_news",
        label="Holo-News",
        topology="public_broadcast",
        audibility_mode="audible_speech",
        requires_vocal_speech=False,
    )
    courier_med = CommunicationMediumBlock(
        medium_id="guild_raven",
        label="Raven Post",
        topology="async_courier",
        audibility_mode="silent_mental_or_text",
        requires_vocal_speech=False,
        requires_somatic_input=True,
        travel_turns_per_hop=3,
    )

    registry = (
        ChannelPresetRegistry()
        .save_preset(
            ChannelPreset(
                preset_id="party_tac",
                label="Squad Tac",
                frequency_or_address="142.8 MHz",
                aliases=("party", "squad", "#party-tac"),
                tier="canonical_ruleset",
            )
        )
        .save_preset(
            ChannelPreset(
                preset_id="port_vane_news",
                label="Port Vane Channel 7",
                frequency_or_address="Ch. 07",
                semantic_tags=("#local-news",),
                location_scope="port_vane",
            )
        )
        .save_preset(
            ChannelPreset(
                preset_id="ashlands_fm",
                label="Wasteland Enclave FM",
                frequency_or_address="94.3 FM",
                semantic_tags=("#local-news",),
                location_scope="ashlands",
            )
        )
    )

    # Location-scoped #local-news lookup
    assert registry.resolve("local-news", location_id="port_vane") is not None
    assert registry.resolve("local-news", location_id="ashlands") is not None
    assert (
        registry.resolve("local-news", location_id="ashlands").frequency_or_address == "94.3 FM"  # type: ignore[union-attr]
    )

    # 1. tuned_frequency + Z-2 subterranean degradation
    deep_speaker = SpeakerAcousticState(
        entity_id="pc_kale",
        name="Kale",
        room_id="cavern_deep",
        z_stratum=-3,
        capability_tags=("handheld_radio",),
    )
    ally = ListenerAcousticState(
        seat_id="s_vane",
        entity_id="comp_vane",
        room_id="surface_camp",
        tuned_channel="#party-tac",
        language_profile=ListenerLanguageProfile(seat_id="s_vane", entity_id="comp_vane"),
    )
    res_radio = resolve_diegetic_transmission(
        deep_speaker,
        "Extraction team come in immediately!",
        [ally],
        medium=radio_med,
        channel_query="party",
        registry=registry,
    )
    assert res_radio.delivered is True
    assert res_radio.signal_quality < 0.7
    assert "...crackle..." in res_radio.deliveries[0].rendered_text
    assert res_radio.resolved_channel is not None
    assert res_radio.resolved_channel.frequency_or_address == "142.8 MHz"

    # 2. mental_link universal conceptual ignores unknown language & anti_psionic suppress
    langs = _sample_languages()
    paralyzed_speaker = SpeakerAcousticState(
        entity_id="pc_kale",
        name="Kale",
        room_id="vault",
        conditions=("paralyzed",),
    )
    shielded_listener = ListenerAcousticState(
        seat_id="s_warden",
        entity_id="npc_warden",
        room_id="vault",
        room_environment_tags=("anti_psionic",),
        language_profile=ListenerLanguageProfile(seat_id="s_warden", entity_id="npc_warden"),
    )
    res_tele = resolve_diegetic_transmission(
        paralyzed_speaker,
        "Help me break this stasis field!",
        [ally, shielded_listener],
        medium=telepathy_med,
        target_entity_id="comp_vane",
        language=langs["elvish"],
        all_languages=langs,
    )
    assert res_tele.delivered is True
    assert res_tele.breaks_stealth is False
    assert [d.entity_id for d in res_tele.deliveries] == ["comp_vane"]
    assert "Help me break this stasis field!" in res_tele.deliveries[0].rendered_text

    # 3. resource_gated_artifact enforces max_words=25 & 5% cross-plane failure
    over_words = " ".join(f"word{i}" for i in range(26))
    res_over = resolve_diegetic_transmission(
        SpeakerAcousticState(entity_id="pc_kale", name="Kale", room_id="tower"),
        over_words,
        [ally],
        medium=sending_med,
    )
    assert res_over.delivered is False
    assert res_over.blocked_reason is not None
    assert "exceeds_max_words" in res_over.blocked_reason

    other_plane_ally = ally.model_copy(update={"dimension_phase": "astral"})
    res_misfire = resolve_diegetic_transmission(
        SpeakerAcousticState(entity_id="pc_kale", name="Kale", room_id="tower"),
        "The seal broke.",
        [other_plane_ally],
        medium=sending_med,
        d100_roll_fn=lambda: 3,
    )
    assert res_misfire.delivered is False
    assert res_misfire.planar_misfire is True

    # 4. persistent_network with handle_pseudonym & deafened listener STILL receives text
    bbs_speaker = SpeakerAcousticState(
        entity_id="pc_kale",
        name="Kale",
        room_id="apt",
        conditions=("muted",),
        channel_handle="Raven_09",
    )
    deaf_bbs_reader = ally.model_copy(
        update={"conditions": ("deafened",), "tuned_channel": "shadowland"}
    )
    res_bbs = resolve_diegetic_transmission(
        bbs_speaker,
        "Uploading corp schematics.",
        [deaf_bbs_reader],
        medium=bbs_med,
        channel_query="shadowland",
    )
    assert res_bbs.delivered is True
    assert "Raven_09" in res_bbs.deliveries[0].rendered_text
    assert "Kale" not in res_bbs.deliveries[0].rendered_text

    # 5. public_broadcast with location-aware station & receiver prop
    tv_listener = ally.model_copy(update={"has_receiver_prop": True, "tuned_channel": None})
    res_tv = resolve_diegetic_transmission(
        SpeakerAcousticState(entity_id="npc_anchor", name="Anchor", room_id="studio"),
        "Curfew begins at dusk.",
        [tv_listener],
        medium=broadcast_med,
        channel_query="local-news",
        registry=registry,
        speaker_location_id="port_vane",
    )
    assert res_tv.delivered is True
    assert "Port Vane Channel 7" in res_tv.deliveries[0].rendered_text

    # 6. async_courier returns InTransitMessage with ETA
    res_courier = resolve_diegetic_transmission(
        SpeakerAcousticState(entity_id="pc_kale", name="Kale", room_id="oakhaven"),
        "Send reinforcements.",
        [ally],
        medium=courier_med,
        target_entity_id="lord_varek",
        courier_dest_node="citadel",
        courier_hops=4,
        attached_items=("wax_sealed_decree",),
    )
    assert res_courier.delivered is True
    assert res_courier.in_transit is not None
    assert res_courier.in_transit.eta_turns == 12
    assert res_courier.in_transit.attached_items == ("wax_sealed_decree",)


@pytest.mark.zero_ai
def test_helmet_isolation_vacuum_gagged_deafened_and_pa_modulation() -> None:
    """Verify #sealed_helmet zero bleed, optional PA VoiceModulator, #vacuum, #gagged, #deafened."""
    suit_radio = CommunicationMediumBlock(
        medium_id="eva_radio",
        label="Suit Radio",
        topology="tuned_frequency",
        audibility_mode="audible_speech",
        requires_vocal_speech=True,
    )

    # Gagged blocks local speech with muffled notice, still allows hand-signs
    gagged = SpeakerAcousticState(
        entity_id="pc_kale",
        name="Kale",
        room_id="dock",
        conditions=("#gagged",),
    )
    bystander = ListenerAcousticState(
        seat_id="s_bystander",
        entity_id="npc_guard",
        room_id="dock",
        tuned_channel="squad",
        language_profile=ListenerLanguageProfile(seat_id="s_bystander", entity_id="npc_guard"),
    )
    res_gag = resolve_diegetic_transmission(gagged, "Untie me!", [bystander])
    assert res_gag.delivered is False
    assert res_gag.muffled_struggle_notice is not None
    assert "behind the gag" in res_gag.muffled_struggle_notice

    res_sign = resolve_diegetic_transmission(
        gagged, "Two guards ahead", [bystander], special_mode="sign"
    )
    assert res_sign.delivered is True
    assert "[Hand-Sign]" in res_sign.deliveries[0].rendered_text

    # Sealed helmet in pressurized room transmits over suit radio with ZERO external room bleed
    helmeted = SpeakerAcousticState(
        entity_id="pc_kale",
        name="Kale",
        room_id="dock",
        conditions=("#sealed_helmet",),
        external_pa_enabled=False,
    )
    un_tuned_bystander = bystander.model_copy(update={"tuned_channel": None})
    tuned_ally = ListenerAcousticState(
        seat_id="s_ally",
        entity_id="comp_vane",
        room_id="orbit_bay",
        tuned_channel="#party-tac",
        language_profile=ListenerLanguageProfile(seat_id="s_ally", entity_id="comp_vane"),
    )
    res_iso = resolve_diegetic_transmission(
        helmeted,
        "Moving into airlock.",
        [un_tuned_bystander, tuned_ally],
        medium=suit_radio,
        channel_query="#party-tac",
    )
    assert res_iso.delivered is True
    assert res_iso.room_bleed_count == 0
    assert res_iso.breaks_stealth is False
    assert [d.entity_id for d in res_iso.deliveries] == ["comp_vane"]

    # External PA speaker enabled with VoiceModulatorProfile (scrambled_anonymous + loud_hailer)
    pa_speaker = helmeted.model_copy(
        update={
            "external_pa_enabled": True,
            "voice_modulator": VoiceModulatorProfile(
                projection="loud_hailer",
                timbre="scrambled_anonymous",
            ),
        }
    )
    res_pa = resolve_diegetic_transmission(
        pa_speaker,
        "Lay down your weapons!",
        [un_tuned_bystander, tuned_ally],
        medium=suit_radio,
        channel_query="#party-tac",
    )
    assert res_pa.delivered is True
    assert res_pa.room_bleed_count == 1
    assert res_pa.room_bleed_hops == 2
    bystander_deliv = next(d for d in res_pa.deliveries if d.entity_id == "npc_guard")
    assert "An Electronically Scrambled Voice" in bystander_deliv.rendered_text

    # Vacuum blocks open-room say, allows touch-helmet and sealed-helmet suit radio
    vac_speaker = helmeted.model_copy(update={"room_environment_tags": ("#vacuum",)})
    res_vac_say = resolve_diegetic_transmission(vac_speaker, "Hello?", [un_tuned_bystander])
    assert res_vac_say.delivered is False
    assert res_vac_say.blocked_reason == "vacuum_no_air"

    res_touch = resolve_diegetic_transmission(
        vac_speaker,
        "Radio jammed, follow me.",
        [un_tuned_bystander],
        special_mode="touch_helmet",
        target_entity_id="npc_guard",
    )
    assert res_touch.delivered is True
    assert "[Helmet Contact]" in res_touch.deliveries[0].rendered_text

    # Deafened observer sees lip movement; lip reader catches partial transcript
    deaf_plain = bystander.model_copy(update={"conditions": ("#deafened",), "can_lip_read": False})
    deaf_reader = bystander.model_copy(
        update={
            "seat_id": "s_lr",
            "entity_id": "pc_lr",
            "conditions": ("deafened",),
            "can_lip_read": True,
        }
    )
    res_deaf = resolve_diegetic_transmission(
        SpeakerAcousticState(entity_id="pc_kale", name="Kale", room_id="dock"),
        "Meet at the pier.",
        [deaf_plain, deaf_reader],
    )
    by_ent = {d.entity_id: d for d in res_deaf.deliveries}
    assert "lips moving, but hear nothing" in by_ent["npc_guard"].rendered_text
    assert by_ent["pc_lr"].lip_read_partial is True
    assert "Meet at the pier." in by_ent["pc_lr"].rendered_text
