"""Unit tests for deterministic MUD command routing, prosody, poses, emotes, whisper & shout."""

from __future__ import annotations

import pytest

from app.mud_parser import (
    BUILTIN_EMOTES,
    RoomTopologyEdge,
    WhisperEavesdropListener,
    list_emote_completions,
    parse_mixed_pose,
    parse_mud_command,
    parse_prosody,
    render_emote,
    render_mixed_pose,
    resolve_emote,
    resolve_shout_propagation,
    resolve_whisper_eavesdrop,
)


@pytest.mark.zero_ai
def test_two_tier_command_routing_and_core_comms() -> None:
    """Verify Tier-1 deterministic routing for core verbs vs Tier-2 narrative fallback."""
    assert parse_mud_command("n").category == "movement"
    assert parse_mud_command("north").category == "movement"
    assert parse_mud_command("look").category == "observation"
    assert parse_mud_command("inventory").category == "inventory"
    assert parse_mud_command("use melee_strike @goblin").category == "vm_action"
    assert parse_mud_command("use melee_strike @goblin").target_token == "goblin"
    assert parse_mud_command("roll 2d6+3").category == "roll"
    assert parse_mud_command("flip coin").category == "roll"

    say_short = parse_mud_command("' Watch the northern archway.")
    assert say_short.category == "communication"
    assert say_short.verb == "say"
    assert say_short.speech is not None
    assert say_short.speech.clean_text == "Watch the northern archway."

    say_to = parse_mud_command('say to @garrick "Did you forge this blade?"')
    assert say_to.verb == "say_to"
    assert say_to.target_token == "garrick"
    assert say_to.speech is not None
    assert say_to.speech.clean_text == "Did you forge this blade?"

    at_say = parse_mud_command('@vane "Watch the stairs."')
    assert at_say.verb == "say_to"
    assert at_say.target_token == "vane"

    ooc = parse_mud_command("// Anyone want a quick short rest?")
    assert ooc.category == "communication"
    assert ooc.verb == "ooc"

    poss = parse_mud_command("::'s eyes narrow.")
    assert poss.category == "emote"
    assert "possessive" in poss.flags

    fallback = parse_mud_command("pry open the rusted grate with the crowbar")
    assert fallback.category == "narrative_fallback"
    assert fallback.tier_route == "tier_2_narrative"


@pytest.mark.zero_ai
def test_prosody_mixed_pose_and_tts_narrator_separation() -> None:
    """Verify emphasis spans, pauses, chanting, target adaptation & TTS/Narrator split."""
    prosody = parse_prosody(
        "*Hold* the **GATE** NOW -- [pause] ~oh guardian~ ...",
        tone="sarcastically",
    )
    assert prosody.valence == "sarcastic_taunt"
    kinds = [s.kind for s in prosody.spans]
    assert "italic" in kinds
    assert "bold" in kinds
    assert "all_caps" in kinds
    assert "pause" in kinds
    assert "chant" in kinds

    beats, targets, valence = parse_mixed_pose(
        "(wearily) leans against the cracked pillar, glances at @vane, "
        '"We can\'t hold this bridge much longer," and draws his parrying dagger.'
    )
    assert targets == ("vane",)
    assert valence == "weary_exasperated"

    rendered = render_mixed_pose(
        "pc_kale",
        "Kale",
        beats,
        entity_names={"vane": "Vane"},
    )
    assert "[[entity:pc_kale|Kale]]" in rendered.to_room
    assert "[[entity:vane|Vane]]" in rendered.to_room
    assert "**you**" in rendered.per_target_views["vane"]
    assert rendered.tts_dialogue_segments == ("We can't hold this bridge much longer,",)
    assert "parrying dagger" in rendered.narrator_action_segments[0]
    assert "bridge much longer" not in rendered.narrator_action_segments[0]


@pytest.mark.zero_ai
def test_60_plus_social_emotes_perspectives_and_autocomplete() -> None:
    """Verify >= 60 built-in emotes, 3-perspective grammar, aliases, valence & completion."""
    assert len(BUILTIN_EMOTES) >= 60

    glare = resolve_emote("glare")
    assert glare is not None
    persp = render_emote(
        glare,
        "Kale",
        target_name="the Cultist Fanatic",
        adverb="coldly",
        speech="Drop the key.",
    )
    assert persp.to_actor == 'You glare coldly at the Cultist Fanatic and say, "Drop the key."'
    assert persp.to_target == 'Kale glares coldly at you and says, "Drop the key."'
    assert persp.to_room == 'Kale glares coldly at the Cultist Fanatic and says, "Drop the key."'
    assert persp.valence == "hostile_intimidation"

    parsed = parse_mud_command('glare @cultist coldly "Drop the key."')
    assert parsed.category == "social_emote"
    assert parsed.verb == "glare"
    assert parsed.target_token == "cultist"
    assert parsed.adverb == "coldly"
    assert parsed.speech is not None
    assert parsed.speech.clean_text == "Drop the key."

    assert resolve_emote("shake") is BUILTIN_EMOTES["handshake"]
    assert "smile" in list_emote_completions("sm")
    assert "smirk" in list_emote_completions("sm")


@pytest.mark.zero_ai
def test_non_interrupting_whisper_and_multi_hop_shout() -> None:
    """Verify non-interrupting whisper eavesdrop tiers and 1-2 hop shout propagation."""
    listeners = [
        WhisperEavesdropListener(entity_id="pc_kale", name="Kale"),
        WhisperEavesdropListener(entity_id="comp_vane", name="Vane"),
        WhisperEavesdropListener(entity_id="gm_seat", name="GM"),
        WhisperEavesdropListener(
            entity_id="npc_spy",
            name="Spy",
            passive_observation=18,
        ),
        WhisperEavesdropListener(
            entity_id="npc_scout",
            name="Scout",
            passive_observation=9,
            active_eavesdrop_target_id="pc_kale",
            roll_bonus=4,
        ),
        WhisperEavesdropListener(
            entity_id="npc_guard",
            name="Guard",
            passive_observation=10,
        ),
    ]
    deliveries = resolve_whisper_eavesdrop(
        "pc_kale",
        "Kale",
        "comp_vane",
        "Vane",
        "Take the left tunnel at midnight",
        listeners,
        gm_ids=("gm_seat",),
        stealth_dc=12,
        background_roll_fn=lambda lst: 9 if lst.entity_id == "npc_scout" else 5,
    )
    by_id = {d.recipient_id: d for d in deliveries}
    assert by_id["pc_kale"].role == "actor"
    assert by_id["comp_vane"].role == "target"
    assert by_id["gm_seat"].role == "gm"
    assert by_id["npc_spy"].role == "eavesdropper_full"
    assert by_id["npc_spy"].leaked_speech == "Take the left tunnel at midnight"
    assert by_id["npc_scout"].role == "eavesdropper_partial"
    assert by_id["npc_scout"].leaked_speech is not None
    assert by_id["npc_guard"].role == "observer"
    assert by_id["npc_guard"].leaked_speech is None
    assert "whispers quietly" in by_id["npc_guard"].rendered_text

    edges = [
        RoomTopologyEdge(
            from_room_id="great_hall",
            to_room_id="corridor",
            direction_label="north",
            from_room_name="Great Hall",
        ),
        RoomTopologyEdge(
            from_room_id="corridor",
            to_room_id="vault",
            direction_label="east",
            from_room_name="Corridor",
        ),
        RoomTopologyEdge(
            from_room_id="great_hall",
            to_room_id="sealed_sanctum",
            direction_label="west",
            from_room_name="Great Hall",
            is_sealed=True,
        ),
        RoomTopologyEdge(
            from_room_id="corridor",
            to_room_id="crypt_below",
            direction_label="down",
            from_room_name="Corridor",
            is_vertical_shaft=True,
        ),
    ]
    shout = resolve_shout_propagation("Kale", "AMBUSH!", "great_hall", edges, max_hops=2)
    assert shout.breaks_stealth is True
    assert shout.alert_clock_delta == 1
    assert "corridor" in shout.adjacent_bleed
    assert "vault" in shout.adjacent_bleed
    assert "crypt_below" in shout.adjacent_bleed
    assert "vertical shaft" in shout.adjacent_bleed["crypt_below"]
    assert "sealed_sanctum" not in shout.adjacent_bleed


@pytest.mark.zero_ai
def test_covert_and_time_control_mud_verbs() -> None:
    """Covert (disguise/hide/steal/plant) and time_control (timeskip/wait) verbs route in <5ms."""
    disguise_list = parse_mud_command("disguise list")
    assert disguise_list.category == "covert"
    assert disguise_list.verb == "disguise"
    assert disguise_list.args == ("list",)

    disguise_save = parse_mud_command("/disguise save envoy_slot")
    assert disguise_save.category == "covert"
    assert disguise_save.args == ("save", "envoy_slot")

    disguise_don = parse_mud_command("disguise don envoy_slot")
    assert disguise_don.category == "covert"
    assert disguise_don.args == ("don", "envoy_slot")

    disguise_swap = parse_mud_command("disguise swap guard_slot")
    assert disguise_swap.category == "covert"
    assert disguise_swap.args == ("swap", "guard_slot")

    disguise_rm = parse_mud_command("disguise remove")
    assert disguise_rm.category == "covert"
    assert disguise_rm.args == ("remove",)

    assert parse_mud_command("hide").category == "covert"
    assert parse_mud_command("sneak").category == "covert"

    steal_cmd = parse_mud_command("steal @guard pouch")
    assert steal_cmd.category == "covert"
    assert steal_cmd.verb == "steal"
    assert steal_cmd.target_token == "guard"
    assert steal_cmd.args == ("@guard", "pouch")

    plant_cmd = parse_mud_command("plant @noble ledger")
    assert plant_cmd.category == "covert"
    assert plant_cmd.verb == "plant"
    assert plant_cmd.target_token == "noble"

    ts_dur = parse_mud_command("timeskip 10m")
    assert ts_dur.category == "time_control"
    assert ts_dur.verb == "timeskip"
    assert ts_dur.args == ("10m",)

    ts_app = parse_mud_command("timeskip approve")
    assert ts_app.category == "time_control"
    assert ts_app.args == ("approve",)

    wait_cmd = parse_mud_command("wait 10m")
    assert wait_cmd.category == "time_control"
    assert wait_cmd.verb == "wait"
    assert wait_cmd.args == ("10m",)
