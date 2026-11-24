"""Unit tests for Flow Controller, Reaction Windows, Derived Stats, and Pure VM Replay."""

from __future__ import annotations

import pytest

from app.ruleset_vm import (
    ActionBlock,
    ConditionBlock,
    EffectSpec,
    EntityState,
    EventHookBlock,
    FlowConfig,
    FormulaError,
    OutcomeTier,
    PackageManifest,
    PropertyBlock,
    RandomizerSpec,
    ResolutionMechanicBlock,
    ResourcePoolBlock,
    RulesetSchema,
    advance_turn,
    apply_sheet_override,
    compute_entity_view,
    delay_turn,
    execute_action,
    handoff_spotlight,
    initialize_scene_state,
    replay_events,
    resolve_pending_reaction,
    start_round_initiative,
    state_hash,
    switch_flow_mode,
)
from app.ruleset_vm.rng import SceneRngRegistry


def _sample_combat_ruleset() -> RulesetSchema:
    return RulesetSchema(
        manifest=PackageManifest(
            package_type="ruleset",
            package_id="tactical_sample",
            name="Tactical Agnostic Sample",
            version="0.1.0",
        ),
        properties={
            "agility": PropertyBlock(prop_id="agility", label="Agility", default_value=14),
            "agility_mod": PropertyBlock(
                prop_id="agility_mod",
                label="Agility Mod",
                formula="floor((@self.agility - 10) / 2)",
            ),
            "defense": PropertyBlock(
                prop_id="defense",
                label="Defense",
                formula="10 + @self.agility_mod",
            ),
        },
        resource_pools={
            "vitality": ResourcePoolBlock(
                pool_id="vitality",
                label="Vitality",
                default_current=20,
                max_formula="20",
            ),
            "stamina": ResourcePoolBlock(
                pool_id="stamina",
                label="Stamina",
                default_current=3,
                max_formula="3",
            ),
        },
        conditions={
            "parrying": ConditionBlock(
                condition_id="parrying",
                label="Parrying",
                property_modifiers={"defense": "2"},
                default_duration_turns=1,
            ),
            "bound": ConditionBlock(
                condition_id="bound",
                label="Bound",
                blocks_tags=("melee",),
            ),
        },
        resolutions={
            "strike_roll": ResolutionMechanicBlock(
                mech_id="strike_roll",
                label="Strike",
                randomizer=RandomizerSpec(kind="dice_formula", formula="1d20"),
                modifier_formula="@self.agility_mod",
                target_formula="@target.defense",
                tiers=(
                    OutcomeTier(
                        tier_id="hit",
                        label="Hit",
                        condition="@roll.total >= @roll.target",
                        effects=(
                            EffectSpec(
                                kind="modify_pool",
                                target_scope="target",
                                target_key="vitality",
                                formula="-5",
                            ),
                        ),
                    ),
                    OutcomeTier(tier_id="miss", label="Miss", condition="true"),
                ),
            )
        },
        actions={
            "slash": ActionBlock(
                action_id="slash",
                label="Slash",
                category="action",
                resolution_id="strike_roll",
                requires="exists(@target) && @target.vitality > 0",
                allow_reactions=True,
                requires_target=True,
                tags=("melee",),
            ),
            "parry": ActionBlock(
                action_id="parry",
                label="Parry",
                category="reaction",
                trigger="on_targeted",
                pool_costs={"stamina": "1"},
                default_effects=(
                    EffectSpec(
                        kind="add_condition",
                        target_scope="self",
                        target_key="parrying",
                    ),
                ),
            ),
        },
        event_hooks={
            "log_slash": EventHookBlock(
                hook_id="log_slash",
                event_name="on_action_resolved",
                condition="@event.action_id == 'slash'",
                effects=(
                    EffectSpec(
                        kind="advance_clock",
                        target_scope="scene",
                        target_key="action_counter",
                        formula="1",
                    ),
                ),
            )
        },
        flow_config=FlowConfig(
            default_mode="round_initiative",
            initiative_formula="1d20 + @self.agility_mod",
        ),
    )


@pytest.mark.zero_ai
def test_ruleset_graph_validation_and_cycle_detection() -> None:
    """RulesetSchema validates cross-references and flags circular derived formulas."""
    rs = _sample_combat_ruleset()
    assert rs.validate_graph() == []

    cyclic = RulesetSchema(
        manifest=rs.manifest,
        properties={
            "stat_a": PropertyBlock(prop_id="stat_a", label="A", formula="@self.stat_b + 1"),
            "stat_b": PropertyBlock(prop_id="stat_b", label="B", formula="@self.stat_a + 1"),
        },
    )
    with pytest.raises(FormulaError) as exc_info:
        cyclic.topological_property_order()
    assert exc_info.value.code == "RPG-E2001"
    assert any("Circular" in err for err in cyclic.validate_graph())


@pytest.mark.zero_ai
def test_pluggable_flow_modes() -> None:
    """Flow controller transitions across round_initiative, delay, popcorn_spotlight & freeform."""
    rs = _sample_combat_ruleset()
    rng = SceneRngRegistry("flow-seed").stream("initiative")
    ent_a = EntityState(entity_id="a", name="Aria", base_properties={"agility": 16})
    ent_b = EntityState(entity_id="b", name="Bram", base_properties={"agility": 12})

    flow = start_round_initiative(
        rs,
        {
            "a": compute_entity_view(rs, ent_a).to_eval_context(),
            "b": compute_entity_view(rs, ent_b).to_eval_context(),
        },
        rng,
    )
    assert flow.mode == "round_initiative"
    assert flow.round_number == 1
    assert set(flow.turn_order) == {"a", "b"}

    first_actor = flow.active_entity_id
    assert first_actor is not None
    flow_delayed = delay_turn(flow, first_actor)
    assert flow_delayed.turn_order[-1] == first_actor
    assert first_actor in flow_delayed.delayed_entities

    flow_r2 = advance_turn(advance_turn(flow))
    assert flow_r2.round_number == 2

    spotlight = switch_flow_mode(
        flow_r2,
        "popcorn_spotlight",
        entity_contexts={"a": {}, "b": {}},
        spotlight_entity_id="a",
    )
    spotlight_2 = handoff_spotlight(spotlight, "b", ("a", "b"))
    spotlight_next_round = handoff_spotlight(spotlight_2, "a", ("a", "b"))
    assert spotlight_next_round.round_number == spotlight.round_number + 1

    freeform = switch_flow_mode(spotlight_next_round, "freeform")
    assert freeform.mode == "freeform"


@pytest.mark.zero_ai
def test_reaction_window_action_execution_manual_override_and_replay() -> None:
    """End-to-end action -> reaction window -> parry -> resolution -> sheet override -> replay."""
    rs = _sample_combat_ruleset()
    attacker = EntityState(entity_id="pc_1", name="Kale", base_properties={"agility": 16})
    defender = EntityState(entity_id="npc_1", name="Sentinel", base_properties={"agility": 14})
    initial = initialize_scene_state(rs, "battle_1", [attacker, defender], scene_seed="combat-42")

    # 1. Execute slash -> pauses in PENDING_REACTION because Sentinel can parry
    paused = execute_action(rs, initial, "pc_1", "slash", target_id="npc_1")
    assert paused.status == "pending_reaction"
    assert paused.pending_window is not None
    assert paused.pending_window.prompts[0].eligible_reaction_ids == ("parry",)

    # 2. Defender submits Parry reaction -> stamina drops, defense increases +2, then slash fires
    completed = resolve_pending_reaction(
        rs,
        paused.state,
        responses=[("npc_1", "parry")],
    )
    assert completed.status == "executed"
    assert completed.state.pending_reaction is None
    assert completed.state.entities["npc_1"].pools["stamina"] == 2
    assert "parrying" in completed.state.entities["npc_1"].conditions
    assert compute_entity_view(rs, completed.state.entities["npc_1"]).properties["defense"] == 14
    assert completed.state.clocks["action_counter"] == 1

    # 3. Verify manual_roll_mode skips automatic dice resolution cleanly
    manual = execute_action(
        rs,
        completed.state,
        "pc_1",
        "slash",
        target_id="npc_1",
        manual_roll_mode=True,
        bypass_reactions=True,
    )
    assert manual.status == "manual_roll_required"
    assert manual.events == ()

    # 4. Verify audited SHEET_OVERRIDE & full deterministic event replay
    overridden_state, override_evt = apply_sheet_override(
        rs,
        completed.state,
        entity_id="pc_1",
        pool_overrides={"stamina": 1},
        actor_seat_id="gm",
        reason="Manual tabletop adjustment",
    )
    assert overridden_state.entities["pc_1"].pools["stamina"] == 1

    # 5. Verify condition tag gating blocks tagged actions
    bound_state = apply_sheet_override(
        rs,
        overridden_state,
        entity_id="pc_1",
        actor_seat_id="gm",
    )[0]
    _ = bound_state
    bound_actor = overridden_state.entities["pc_1"].model_copy(
        update={
            "conditions": {
                "bound": overridden_state.entities["npc_1"]
                .conditions["parrying"]
                .model_copy(update={"condition_id": "bound"})
            }
        }
    )
    gated_scene = overridden_state.model_copy(
        update={"entities": {**overridden_state.entities, "pc_1": bound_actor}}
    )
    with pytest.raises(PermissionError):
        execute_action(rs, gated_scene, "pc_1", "slash", target_id="npc_1")

    full_events = [*paused.events, *completed.events, override_evt]
    replayed = replay_events(rs, initial, full_events)
    assert state_hash(replayed) == state_hash(overridden_state)
