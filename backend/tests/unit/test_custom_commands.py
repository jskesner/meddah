"""Unit tests for Host-Created Custom Emotes, 4-Step ECA Custom Commands & Aliases."""

from __future__ import annotations

import pytest

from app.mud_parser import (
    ChannelingSpec,
    ClientCommandAliases,
    CommandActionPipeline,
    CommandActorContext,
    CommandAuthorRole,
    CommandCostSpec,
    CommandPayload,
    CommandResolutionStep,
    CustomCommandRegistry,
    CustomEmoteBlock,
    CustomMudCommandBlock,
    RandomTableOutcome,
    execute_custom_command,
    parse_mud_command,
    render_emote,
    resolve_emote,
    tick_channeling_task,
)
from app.ruleset_vm import evaluate_formula


@pytest.mark.zero_ai
def test_custom_command_rbac_and_autocomplete_visibility() -> None:
    """Verify RBAC authoring gate and scoped autocomplete palette synchronization."""
    registry = CustomCommandRegistry()
    regular_player = CommandAuthorRole(seat_id="p1", is_host=False, is_gm=False)
    authorized_gm = CommandAuthorRole(
        seat_id="gm1", is_host=False, is_gm=True, can_manage_custom_commands=True
    )

    custom_emote = CustomEmoteBlock(
        emote_id="emote_flourish",
        verb="flourish",
        aliases=("twirlcape",),
        no_target_actor="You swirl your cloak{adv} in a theatrical flourish.",
        no_target_room="{actor} swirls a cloak{adv} in a theatrical flourish.",
        targeted_actor="You execute a sweeping cloak flourish{adv} before {target}.",
        targeted_target="{actor} executes a sweeping cloak flourish{adv} before you.",
        targeted_room="{actor} executes a sweeping cloak flourish{adv} before {target}.",
        valence="respectful_greeting",
        scope="room_or_poi_only",
        scope_target_id="grand_theatre",
    )
    shrine_cmd = CustomMudCommandBlock(
        command_id="cmd_toss_coin",
        verb="toss_coin",
        scope="room_or_poi_only",
        scope_target_id="fountain_shrine",
        eligibility="requires_tag_or_faction",
        required_tags=("silver_pilgrim",),
        pipeline=CommandActionPipeline(
            requires="has_tag(@room, 'shrine')",
            failure_notice="You must stand beside the consecrated shrine.",
            costs=(CommandCostSpec(pool_id="silver_coin", amount=1),),
            resolution_step=CommandResolutionStep(
                kind="random_table",
                table_die_sides=100,
                table_outcomes=(
                    RandomTableOutcome(min_roll=1, max_roll=60, branch="partial", label="Ripple"),
                    RandomTableOutcome(
                        min_roll=61, max_roll=100, branch="success", label="Golden Omen"
                    ),
                ),
            ),
            on_success=(
                CommandPayload(
                    kind="mud_text",
                    room_text="{actor} tosses a coin into the fountain; a golden omen shines!",
                    actor_text="You gain the shrine's blessing.",
                ),
                CommandPayload(kind="add_condition", target_scope="actor", target_key="blessed"),
            ),
            on_partial=(
                CommandPayload(
                    kind="mud_text",
                    room_text="{actor} tosses a silver coin; ripples vanish quietly.",
                ),
            ),
        ),
    )

    with pytest.raises(PermissionError):
        registry.register_emote(regular_player, custom_emote)
    with pytest.raises(PermissionError):
        registry.register_command(regular_player, shrine_cmd)

    registry = registry.register_emote(authorized_gm, custom_emote).register_command(
        authorized_gm, shrine_cmd
    )

    theatre_actor = CommandActorContext(
        actor_id="pc_1",
        actor_name="Lyra",
        room_id="grand_theatre",
    )
    other_actor = CommandActorContext(
        actor_id="pc_2",
        actor_name="Kael",
        room_id="dark_sewer",
    )
    assert "flourish" in registry.autocomplete_entries_for(theatre_actor, "fl")
    assert "flourish" not in registry.autocomplete_entries_for(other_actor, "fl")

    shrine_pilgrim = CommandActorContext(
        actor_id="pc_1",
        actor_name="Lyra",
        room_id="fountain_shrine",
        room_tags=("shrine",),
        tags=("silver_pilgrim",),
        pools={"silver_coin": 2},
    )
    assert "toss_coin" in registry.autocomplete_entries_for(shrine_pilgrim, "to")
    assert "toss_coin" not in registry.autocomplete_entries_for(other_actor, "to")

    # Resolve & render custom emote via social library
    spec = resolve_emote(
        "twirlcape", {e.verb: e.to_emote_spec() for e in registry.visible_emotes_for(theatre_actor)}
    )
    assert spec is not None
    persp = render_emote(spec, "Lyra", target_name="Lord Vane")
    assert persp.to_target == "Lyra executes a sweeping cloak flourish before you."


@pytest.mark.zero_ai
def test_four_step_eca_pipeline_with_vm_ast_evaluator() -> None:
    """Exercise all 4 ECA pipeline steps using VM evaluate_formula + channeling ticks."""
    host = CommandAuthorRole(seat_id="host", is_host=True)
    duel_cmd = CustomMudCommandBlock(
        command_id="cmd_duel",
        verb="duel",
        requires_target=True,
        pipeline=CommandActionPipeline(
            requires="!@self.in_combat",
            failure_notice="Cannot issue a formal duel while already in combat.",
            costs=(CommandCostSpec(pool_id="resolve_token", amount=1),),
            resolution_step=CommandResolutionStep(
                kind="target_confirmation",
                confirmation_prompt="{actor} throws down a glove before {target}. Accept duel?",
            ),
            on_success=(
                CommandPayload(
                    kind="mud_text",
                    actor_text="You cross blades with {target}!",
                    target_text="{actor} accepts and raises guard against you!",
                    room_text="{actor} and {target} begin a formal honor duel.",
                ),
            ),
            on_failure=(
                CommandPayload(
                    kind="mud_text",
                    room_text="{target} declines the honor duel.",
                ),
            ),
        ),
    )
    recall_cmd = CustomMudCommandBlock(
        command_id="cmd_recall",
        verb="recall",
        pipeline=CommandActionPipeline(
            requires="!@self.in_combat && has_tag(@self, 'hearthstone_bound')",
            failure_notice="Must be outside combat and bound to a hearthstone.",
            costs=(CommandCostSpec(pool_id="focus_points", amount=1),),
            on_success=(
                CommandPayload(
                    kind="mud_text",
                    room_text="{actor} begins channeling a beacon home.",
                ),
            ),
            channeling=ChannelingSpec(
                channel_condition_id="channeling_recall",
                duration_turns=2,
                interrupt_on_move=True,
                interrupt_on_damage=True,
                completion_effects=(
                    CommandPayload(
                        kind="teleport",
                        target_scope="actor",
                        target_key="oakhaven_inn",
                        room_text="{actor} vanishes in a flash of hearthlight.",
                    ),
                ),
            ),
        ),
    )

    registry = (
        CustomCommandRegistry().register_command(host, duel_cmd).register_command(host, recall_cmd)
    )
    actor = CommandActorContext(
        actor_id="pc_1",
        actor_name="Kael",
        room_id="arena",
        tags=("hearthstone_bound",),
        pools={"resolve_token": 1, "focus_points": 2},
    )

    # Target confirmation pending -> declined -> accepted
    pending = execute_custom_command(
        registry,
        "duel",
        actor,
        target_id="npc_knight",
        target_name="Sir Rowan",
        eval_predicate=evaluate_formula,
    )
    assert pending.status == "pending_confirmation"
    assert pending.costs_deducted == {}
    assert pending.pending_confirmation is not None
    assert "Sir Rowan" in pending.pending_confirmation.prompt_text

    accepted = execute_custom_command(
        registry,
        "duel",
        actor,
        target_id="npc_knight",
        target_name="Sir Rowan",
        eval_predicate=evaluate_formula,
        target_accepted=True,
    )
    assert accepted.status == "executed"
    assert accepted.costs_deducted == {"resolve_token": 1}
    assert accepted.effects[0].room_text == "Kael and Sir Rowan begin a formal honor duel."

    # Channeling completion after 2 ticks vs interruption on move
    ch_res = execute_custom_command(registry, "recall", actor, eval_predicate=evaluate_formula)
    assert ch_res.status == "channeling_started"
    assert ch_res.channeling_task is not None

    status_1, task_1, done_1 = tick_channeling_task(ch_res.channeling_task)
    assert status_1 == "channeling"
    assert task_1 is not None
    assert task_1.remaining_turns == 1
    assert done_1 == ()

    status_2, task_2, done_2 = tick_channeling_task(task_1)
    assert status_2 == "completed"
    assert task_2 is None
    assert done_2[0].kind == "teleport"
    assert done_2[0].target_key == "oakhaven_inn"

    interrupted_status, _, _ = tick_channeling_task(ch_res.channeling_task, moved=True)
    assert interrupted_status == "interrupted"


@pytest.mark.zero_ai
def test_client_command_aliases_expansion() -> None:
    """Verify personal > alias macros expand cleanly into validated MUD commands."""
    aliases = ClientCommandAliases().define_alias("eb", 'cast "Eldritch Blast" @1')
    assert aliases.expand("eb @goblin") == 'cast "Eldritch Blast" @goblin'

    parsed = parse_mud_command("eb @goblin", client_aliases=aliases.aliases)
    assert parsed.category == "vm_action"
    assert parsed.verb == "cast"
    assert parsed.target_token == "goblin"
    assert "alias_expanded" in parsed.flags

    cleared = aliases.remove_alias("eb")
    assert cleared.aliases == {}
