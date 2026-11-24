"""Latency budget benchmarks proving <5ms deterministic MUD parser & comms resolution."""

from __future__ import annotations

import time

import pytest

from app.mud_parser import (
    ChannelPreset,
    ChannelPresetRegistry,
    CommandActionPipeline,
    CommandActorContext,
    CommandAuthorRole,
    CommandCostSpec,
    CommandPayload,
    CommunicationMediumBlock,
    CustomCommandRegistry,
    CustomMudCommandBlock,
    LanguageBlock,
    ListenerAcousticState,
    ListenerLanguageProfile,
    SpeakerAcousticState,
    execute_custom_command,
    filter_message_for_listener,
    parse_mud_command,
    render_emote,
    resolve_diegetic_transmission,
    resolve_emote,
)


def _p95_ms(durations_sec: list[float]) -> float:
    ordered = sorted(durations_sec)
    idx = min(len(ordered) - 1, int(0.95 * len(ordered)))
    return ordered[idx] * 1000.0


@pytest.mark.zero_ai
@pytest.mark.perf
def test_mud_parser_and_comms_under_5ms_p95() -> None:
    """Measure 250 calls per pipeline stage and assert p95 latency stays strictly < 5.0 ms."""
    iterations = 250

    glare = resolve_emote("glare")
    assert glare is not None

    elvish = LanguageBlock(
        language_id="elvish",
        label="High Elven",
        family_group="elven_family",
    )
    outsider = ListenerLanguageProfile(seat_id="s_out", entity_id="pc_3")

    radio = CommunicationMediumBlock(
        medium_id="radio",
        label="Squad Radio",
        topology="tuned_frequency",
        audibility_mode="audible_speech",
        requires_vocal_speech=True,
    )
    registry = ChannelPresetRegistry().save_preset(
        ChannelPreset(
            preset_id="party_tac",
            label="Squad Tac",
            frequency_or_address="142.8 MHz",
            aliases=("party",),
        )
    )
    speaker = SpeakerAcousticState(
        entity_id="pc_kale",
        name="Kale",
        room_id="bridge",
        conditions=("sealed_helmet",),
    )
    listeners = [
        ListenerAcousticState(
            seat_id=f"s_{i}",
            entity_id=f"ent_{i}",
            room_id="bridge" if i % 2 == 0 else "engine_room",
            tuned_channel="party",
            language_profile=ListenerLanguageProfile(
                seat_id=f"s_{i}",
                entity_id=f"ent_{i}",
                fluent_languages=("elvish",) if i % 2 == 0 else (),
            ),
        )
        for i in range(6)
    ]

    host = CommandAuthorRole(seat_id="host", is_host=True)
    cmd_reg = CustomCommandRegistry().register_command(
        host,
        CustomMudCommandBlock(
            command_id="toss_coin",
            verb="toss_coin",
            pipeline=CommandActionPipeline(
                requires="has_tag(@room, 'shrine')",
                costs=(CommandCostSpec(pool_id="silver_coin", amount=1),),
                on_success=(
                    CommandPayload(
                        kind="mud_text",
                        room_text="{actor} tosses a silver coin into the basin.",
                    ),
                ),
            ),
        ),
    )
    cmd_actor = CommandActorContext(
        actor_id="pc_kale",
        actor_name="Kale",
        room_id="fountain",
        room_tags=("shrine",),
        pools={"silver_coin": 10},
    )

    sample_cmds = (
        'act (wearily) leans against the pillar, @vane, "Hold fast!"',
        'radio party in elvish (urgently) "Move to extraction!"',
        'glare @cultist coldly "Drop the key."',
        "// anyone ready for camp?",
        "use melee_strike @goblin",
    )

    parse_times: list[float] = []
    emote_times: list[float] = []
    lang_times: list[float] = []
    comms_times: list[float] = []
    custom_times: list[float] = []

    for idx in range(iterations):
        raw = sample_cmds[idx % len(sample_cmds)]

        t0 = time.perf_counter()
        _ = parse_mud_command(raw, custom_verbs=("toss_coin",))
        parse_times.append(time.perf_counter() - t0)

        t0 = time.perf_counter()
        _ = render_emote(glare, "Kale", target_name="Cultist", adverb="coldly", speech="Halt.")
        emote_times.append(time.perf_counter() - t0)

        t0 = time.perf_counter()
        _ = filter_message_for_listener(
            "Kale", "Meet beside the northern stone arch", elvish, outsider
        )
        lang_times.append(time.perf_counter() - t0)

        t0 = time.perf_counter()
        _ = resolve_diegetic_transmission(
            speaker,
            "Sweep the lower catwalk and secure the vault door.",
            listeners,
            medium=radio,
            channel_query="party",
            registry=registry,
            language=elvish,
        )
        comms_times.append(time.perf_counter() - t0)

        t0 = time.perf_counter()
        _ = execute_custom_command(cmd_reg, "toss_coin", cmd_actor)
        custom_times.append(time.perf_counter() - t0)

    assert _p95_ms(parse_times) < 5.0
    assert _p95_ms(emote_times) < 5.0
    assert _p95_ms(lang_times) < 5.0
    assert _p95_ms(comms_times) < 5.0
    assert _p95_ms(custom_times) < 5.0
