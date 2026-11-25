"""Unit tests for Universal Character Transformations & Alternate Forms (ADR-0133)."""

from __future__ import annotations

import pytest

from app.ruleset_vm import (
    DEFAULT_MAX_HOOK_DEPTH,
    ActionBlock,
    ActiveCondition,
    ConditionBlock,
    EffectSpec,
    EntityState,
    EventHookBlock,
    FormBlock,
    FormPoolSpec,
    OutcomeTier,
    PackageManifest,
    PropertyBlock,
    RandomizerSpec,
    ResolutionMechanicBlock,
    ResourcePoolBlock,
    RulesetSchema,
    VmEvent,
    can_shift_into_form,
    compute_entity_view,
    execute_action,
    initialize_scene_state,
    list_available_forms,
    replay_events,
    resolve_pending_reaction,
    revert_form,
    shift_into_form,
    state_hash,
    tick_active_form,
    trigger_event_hooks,
)


def _forms_test_ruleset() -> RulesetSchema:
    return RulesetSchema(
        manifest=PackageManifest(
            package_type="ruleset",
            package_id="forms_test_ruleset",
            name="Forms Test Ruleset",
            version="0.1.0",
        ),
        properties={
            "might": PropertyBlock(prop_id="might", label="Might", default_value=10),
            "agility": PropertyBlock(prop_id="agility", label="Agility", default_value=12),
            "cognition": PropertyBlock(prop_id="cognition", label="Cognition", default_value=16),
            "defense": PropertyBlock(
                prop_id="defense",
                label="Defense",
                formula="10 + floor((@self.agility - 10) / 2)",
            ),
        },
        resource_pools={
            "vitality": ResourcePoolBlock(
                pool_id="vitality",
                label="Vitality",
                default_current=20,
                max_formula="20",
                min_value=0,
            ),
            "shape_charges": ResourcePoolBlock(
                pool_id="shape_charges",
                label="Shift Charges",
                default_current=2,
                max_formula="2",
                min_value=0,
            ),
        },
        resolutions={
            "fixed_hit": ResolutionMechanicBlock(
                mech_id="fixed_hit",
                label="Fixed Impact",
                randomizer=RandomizerSpec(kind="none", base_value=10),
                tiers=(
                    OutcomeTier(
                        tier_id="strike",
                        label="Strike",
                        condition="true",
                        effects=(
                            EffectSpec(
                                kind="modify_pool",
                                target_scope="target",
                                target_key="vitality",
                                formula="-15",
                            ),
                        ),
                    ),
                ),
            ),
        },
        actions={
            "heavy_blow": ActionBlock(
                action_id="heavy_blow",
                label="Heavy Blow",
                category="action",
                resolution_id="fixed_hit",
                requires_target=True,
                tags=("martial",),
            ),
            "cast_ritual": ActionBlock(
                action_id="cast_ritual",
                label="Cast Ritual",
                category="action",
                tags=("verbal_ritual",),
            ),
        },
        forms={
            "dire_wolf": FormBlock(
                form_id="dire_wolf",
                label="Dire Wolf",
                requires="!has_condition(@self, 'bound')",
                pool_costs={"shape_charges": "1"},
                property_mode="replace_subset",
                property_values={"might": 18, "agility": 16},
                pool_policies={
                    "vitality": FormPoolSpec(
                        mode="separate_form_pool",
                        initial_formula="10",
                        max_formula="10",
                        overflow_to_base=True,
                        auto_revert_on_zero=True,
                    ),
                },
                action_mode="replace",
                granted_actions=("claw_rend", "pack_howl"),
                blocked_tags=("verbal_ritual",),
                granted_tags=("beast_form", "quadruped"),
                gear_handling="merge_into_form",
                suppress_gear_auras=True,
                default_duration_turns=3,
                size_category="large",
                anatomy_topology_override="quadruped_beast",
                portrait_override_ref="assets/wolf.svg",
                token_override_ref="assets/wolf_token.png",
            ),
            "mech_exoshell": FormBlock(
                form_id="mech_exoshell",
                label="Siege Exo-Shell",
                property_mode="replace_all",
                property_values={"might": 22, "agility": 8, "cognition": 10},
                pool_policies={
                    "vitality": FormPoolSpec(
                        mode="temp_bonus_pool",
                        initial_formula="8",
                        max_formula="8",
                        overflow_to_base=True,
                        auto_revert_on_zero=True,
                    ),
                },
                action_mode="merge",
                granted_actions=("rail_cannon",),
                granted_tags=("armored_chassis",),
                gear_handling="keep_worn",
                suppress_gear_auras=False,
            ),
            "shadow_aspect": FormBlock(
                form_id="shadow_aspect",
                label="Shadow Aspect",
                property_mode="delta_overlay",
                property_deltas={"agility": "4"},
                pool_policies={
                    "vitality": FormPoolSpec(mode="shared_base_pool"),
                },
                granted_tags=("shadow_phase",),
                gear_handling="keep_worn",
                suppress_gear_auras=False,
            ),
        },
    )


@pytest.mark.zero_ai
def test_dormancy_and_ruleset_graph_validation() -> None:
    """Rulesets without forms remain completely dormant and validation catches bad formulas."""
    rs_with_forms = _forms_test_ruleset()
    assert rs_with_forms.validate_graph() == []

    rs_empty = rs_with_forms.model_copy(update={"forms": {}})
    ent = EntityState(entity_id="pc_1", name="Rowan")
    assert list_available_forms(rs_empty, ent, include_all_ruleset_forms=True) == ()

    bad_rs = rs_with_forms.model_copy(
        update={
            "forms": {
                "bad": FormBlock(
                    form_id="bad",
                    label="Bad",
                    pool_costs={"nonexistent_pool": "1"},
                    property_deltas={"might": "1 +"},
                )
            }
        }
    )
    errs = bad_rs.validate_graph()
    assert len(errs) == 2


@pytest.mark.zero_ai
def test_three_property_modes_auras_actions_and_tag_gating() -> None:
    """Exercise replace_subset, replace_all, delta_overlay, auras, action_mode & gating."""
    rs = _forms_test_ruleset()
    druid = EntityState(
        entity_id="pc_druid",
        name="Sylva",
        base_properties={"might": 9, "agility": 12, "cognition": 18},
        pools={"vitality": 20, "shape_charges": 2},
        tags=("circle_initiate",),
        aura_modifiers={"defense": 3},
        granted_actions=("cast_ritual",),
        available_forms=("dire_wolf",),
    )
    scene = initialize_scene_state(rs, "grove", [druid])

    # Unlocked check & listing
    assert [f.form_id for f in list_available_forms(rs, druid)] == ["dire_wolf"]
    ok, reason = can_shift_into_form(rs, druid, "mech_exoshell", require_unlocked=True)
    assert ok is False
    assert reason is not None

    # 1. replace_subset (Dire Wolf): mental stat stays 18, physical stats change, aura suppressed
    wolf_res = shift_into_form(rs, scene, "pc_druid", "dire_wolf", require_unlocked=True)
    assert wolf_res.costs_deducted == {"shape_charges": 1}
    assert wolf_res.gear_handling == "merge_into_form"
    wolf_ent = wolf_res.state.entities["pc_druid"]
    wolf_view = compute_entity_view(rs, wolf_ent)
    assert wolf_view.active_form_id == "dire_wolf"
    assert wolf_view.properties["might"] == 18
    assert wolf_view.properties["agility"] == 16
    assert wolf_view.properties["cognition"] == 18
    # Derived defense = 10 + floor((16 - 10)/2) = 13 (aura +3 suppressed)
    assert wolf_view.properties["defense"] == 13
    assert wolf_view.granted_actions == ("claw_rend", "pack_howl")
    assert "beast_form" in wolf_view.tags
    assert "circle_initiate" in wolf_view.tags
    assert wolf_view.pools["vitality"] == 10
    assert wolf_view.pool_maxes["vitality"] == 10

    # Verbal rituals blocked in beast form via blocked_tags
    with pytest.raises(PermissionError):
        execute_action(rs, wolf_res.state, "pc_druid", "cast_ritual")

    # 2. replace_all (Mech Exo-Shell): cognition reset to 10, gear aura NOT suppressed, action merge
    mech_res = shift_into_form(rs, scene, "pc_druid", "mech_exoshell")
    mech_view = compute_entity_view(rs, mech_res.state.entities["pc_druid"])
    assert mech_view.properties["might"] == 22
    assert mech_view.properties["cognition"] == 10
    # agility=8 -> dex mod=-1; 10 - 1 + 3(aura) = 12
    assert mech_view.properties["defense"] == 12
    assert mech_view.granted_actions == ("cast_ritual", "rail_cannon")
    assert mech_view.pools["vitality"] == 28
    assert mech_view.pool_maxes["vitality"] == 28

    # 3. delta_overlay (Shadow Aspect): agility 12 + 4 = 16, defense = 13 + 3(aura) = 16
    shadow_res = shift_into_form(rs, scene, "pc_druid", "shadow_aspect")
    shadow_view = compute_entity_view(rs, shadow_res.state.entities["pc_druid"])
    assert shadow_view.properties["agility"] == 16
    assert shadow_view.properties["cognition"] == 18
    assert shadow_view.properties["defense"] == 16
    assert shadow_view.pools["vitality"] == 20


@pytest.mark.zero_ai
def test_pool_spillover_auto_revert_timed_ticks_and_replay() -> None:
    """Verify separate_form_pool spillover, auto-revert, temp bonus absorb, ticks & replay."""
    rs = _forms_test_ruleset()
    druid = EntityState(
        entity_id="pc_druid",
        name="Sylva",
        base_properties={"might": 10, "agility": 12, "cognition": 16},
        pools={"vitality": 20, "shape_charges": 2},
        available_forms=("dire_wolf", "mech_exoshell"),
    )
    foe = EntityState(entity_id="foe_orc", name="Brute", pools={"vitality": 25, "shape_charges": 0})
    initial = initialize_scene_state(rs, "arena", [druid, foe], scene_seed="forms-seed-1")
    all_events: list[VmEvent] = []

    # Timed countdown tick (3 -> 1 -> auto revert on 0)
    shift_1 = shift_into_form(rs, initial, "pc_druid", "dire_wolf")
    all_events.extend(shift_1.events)
    tick_1 = tick_active_form(rs, shift_1.state, "pc_druid", turns=2)
    all_events.extend(tick_1.events)
    assert tick_1.active_form is not None
    assert tick_1.active_form.remaining_turns == 1

    tick_2 = tick_active_form(rs, tick_1.state, "pc_druid", turns=1)
    all_events.extend(tick_2.events)
    assert tick_2.active_form is None
    assert tick_2.state.entities["pc_druid"].active_form is None

    # Re-shift into Dire Wolf (form vitality 10) and take -15 hit -> form hits 0, auto-reverts,
    # and -5 overflows cleanly onto base vitality (20 -> 15)!
    shift_2 = shift_into_form(rs, tick_2.state, "pc_druid", "dire_wolf")
    all_events.extend(shift_2.events)
    strike = execute_action(rs, shift_2.state, "foe_orc", "heavy_blow", target_id="pc_druid")
    all_events.extend(strike.events)
    after_hit = strike.state.entities["pc_druid"]
    assert after_hit.active_form is None
    assert after_hit.pools["vitality"] == 15

    # Shift into mech_exoshell (temp_bonus_pool = +8 on top of 15 = 23) and take -15 hit:
    # bonus absorbs 8 and auto-reverts, 7 spills onto base (15 - 7 = 8)!
    shift_3 = shift_into_form(rs, strike.state, "pc_druid", "mech_exoshell")
    all_events.extend(shift_3.events)
    strike_2 = execute_action(rs, shift_3.state, "foe_orc", "heavy_blow", target_id="pc_druid")
    all_events.extend(strike_2.events)
    after_mech_hit = strike_2.state.entities["pc_druid"]
    assert after_mech_hit.active_form is None
    assert after_mech_hit.pools["vitality"] == 8

    # Manual revert after shifting into shadow_aspect
    shift_4 = shift_into_form(rs, strike_2.state, "pc_druid", "shadow_aspect")
    rev_4 = revert_form(rs, shift_4.state, "pc_druid")
    all_events.extend([*shift_4.events, *rev_4.events])
    assert rev_4.state.entities["pc_druid"].active_form is None

    replayed = replay_events(rs, initial, all_events)
    assert state_hash(replayed) == state_hash(rev_4.state)


def _spell_and_hook_ruleset() -> RulesetSchema:
    return RulesetSchema(
        manifest=PackageManifest(
            package_type="ruleset",
            package_id="spell_hook_forms",
            name="Spell & Hook Forms",
            version="0.1.0",
        ),
        properties={
            "might": PropertyBlock(prop_id="might", label="Might", default_value=10),
            "agility": PropertyBlock(prop_id="agility", label="Agility", default_value=12),
        },
        resource_pools={
            "vitality": ResourcePoolBlock(
                pool_id="vitality",
                label="Vitality",
                default_current=20,
                max_formula="20",
                min_value=0,
            ),
            "arcane_focus": ResourcePoolBlock(
                pool_id="arcane_focus",
                label="Arcane Focus",
                default_current=3,
                max_formula="3",
                min_value=0,
            ),
        },
        conditions={
            "warded": ConditionBlock(condition_id="warded", label="Warded"),
            "frenzied": ConditionBlock(condition_id="frenzied", label="Frenzied"),
            "exhausted": ConditionBlock(condition_id="exhausted", label="Exhausted"),
            "hex_anchor": ConditionBlock(condition_id="hex_anchor", label="Hex Anchor"),
        },
        resolutions={
            "resist_hex": ResolutionMechanicBlock(
                mech_id="resist_hex",
                label="Resist Hex",
                randomizer=RandomizerSpec(kind="none", base_value=5),
                tiers=(
                    OutcomeTier(
                        tier_id="fail",
                        label="Fail",
                        condition="@roll.total < 10",
                        effects=(
                            EffectSpec(
                                kind="shift_form",
                                target_scope="target",
                                target_key="sheep",
                                duration_turns=5,
                                forced=True,
                            ),
                        ),
                    ),
                ),
            ),
            "heavy_crush": ResolutionMechanicBlock(
                mech_id="heavy_crush",
                label="Heavy Crush",
                randomizer=RandomizerSpec(kind="none", base_value=0),
                tiers=(
                    OutcomeTier(
                        tier_id="hit",
                        label="Hit",
                        condition="true",
                        effects=(
                            EffectSpec(
                                kind="modify_pool",
                                target_scope="target",
                                target_key="vitality",
                                formula="-6",
                            ),
                        ),
                    ),
                ),
            ),
        },
        actions={
            "polymorph_hex": ActionBlock(
                action_id="polymorph_hex",
                label="Polymorph Hex",
                category="power",
                resolution_id="resist_hex",
                pool_costs={"arcane_focus": "1"},
                allow_reactions=True,
                requires_target=True,
                tags=("spellcraft",),
            ),
            "counter_ward": ActionBlock(
                action_id="counter_ward",
                label="Counter Ward",
                category="reaction",
                trigger="on_targeted",
                requires="has_condition(@self, 'warded')",
            ),
            "attempt_self_release": ActionBlock(
                action_id="attempt_self_release",
                label="Attempt Self Release",
                category="action",
                default_effects=(
                    EffectSpec(kind="revert_form", target_scope="self", forced=False),
                ),
            ),
            "mismatched_dispel": ActionBlock(
                action_id="mismatched_dispel",
                label="Mismatched Dispel",
                category="power",
                requires_target=True,
                default_effects=(
                    EffectSpec(
                        kind="revert_form",
                        target_scope="target",
                        target_key="wolf",
                        forced=True,
                    ),
                ),
            ),
            "dispel_sheep": ActionBlock(
                action_id="dispel_sheep",
                label="Dispel Sheep",
                category="power",
                requires_target=True,
                default_effects=(
                    EffectSpec(
                        kind="revert_form",
                        target_scope="target",
                        target_key="sheep",
                        formula="dispelled",
                        forced=True,
                    ),
                ),
            ),
            "cleanse_curse": ActionBlock(
                action_id="cleanse_curse",
                label="Cleanse Curse",
                category="power",
                requires_target=True,
                default_effects=(
                    EffectSpec(
                        kind="remove_condition",
                        target_scope="target",
                        target_key="hex_anchor",
                    ),
                ),
            ),
            "smash": ActionBlock(
                action_id="smash",
                label="Smash",
                category="action",
                resolution_id="heavy_crush",
                requires_target=True,
            ),
        },
        forms={
            "sheep": FormBlock(
                form_id="sheep",
                label="Woolly Sheep",
                requires="!has_condition(@self, 'warded')",
                pool_costs={"arcane_focus": "2"},
                property_mode="replace_subset",
                property_values={"might": 3, "agility": 8},
                pool_policies={
                    "vitality": FormPoolSpec(
                        mode="separate_form_pool",
                        initial_formula="4",
                        max_formula="4",
                        overflow_to_base=True,
                        auto_revert_on_zero=True,
                    ),
                },
                blocked_tags=("spellcraft",),
                default_duration_turns=3,
            ),
            "wolf": FormBlock(
                form_id="wolf",
                label="Dire Wolf",
                property_mode="replace_subset",
                property_values={"might": 17, "agility": 16},
            ),
            "werewolf": FormBlock(
                form_id="werewolf",
                label="Full-Moon Lycanthrope",
                property_mode="delta_overlay",
                property_deltas={"might": "6"},
            ),
        },
        event_hooks={
            "moon_curse": EventHookBlock(
                hook_id="moon_curse",
                event_name="on_moon_phase_changed",
                condition="@event.phase == 'full' && has_tag(@self, 'lycanthrope')",
                effects=(
                    EffectSpec(
                        kind="shift_form",
                        target_scope="self",
                        target_key="werewolf",
                        forced=True,
                    ),
                ),
            ),
            "wolf_frenzy": EventHookBlock(
                hook_id="wolf_frenzy",
                event_name="on_form_entered",
                condition="@event.form_id == 'werewolf'",
                effects=(
                    EffectSpec(
                        kind="add_condition",
                        target_scope="self",
                        target_key="frenzied",
                    ),
                ),
            ),
            "shift_fatigue": EventHookBlock(
                hook_id="shift_fatigue",
                event_name="on_form_reverted",
                condition="@event.form_id == 'werewolf' || @event.form_id == 'sheep'",
                effects=(
                    EffectSpec(
                        kind="add_condition",
                        target_scope="self",
                        target_key="exhausted",
                    ),
                ),
            ),
            "break_hex_anchor": EventHookBlock(
                hook_id="break_hex_anchor",
                event_name="on_condition_changed",
                condition="@event.op == 'remove' && @event.condition_id == 'hex_anchor'",
                effects=(
                    EffectSpec(
                        kind="revert_form",
                        target_scope="self",
                        formula="anchor_removed",
                        forced=True,
                    ),
                ),
            ),
            "scene_clock_tick": EventHookBlock(
                hook_id="scene_clock_tick",
                event_name="on_scene_pulse",
                condition="@event.tick > 0",
                effects=(
                    EffectSpec(
                        kind="modify_pool",
                        target_scope="self",
                        target_key="vitality",
                        formula="-1",
                    ),
                    EffectSpec(
                        kind="advance_clock",
                        target_scope="scene",
                        target_key="moon_cycle",
                        formula="1",
                    ),
                ),
            ),
        },
    )


@pytest.mark.zero_ai
def test_hostile_spell_reaction_forced_shift_locks_and_dispel() -> None:
    """Hostile ActionBlock + ReactionWindow + OutcomeTier forces form shift & locks revert."""
    rs = _spell_and_hook_ruleset()
    assert rs.validate_graph() == []

    mage = EntityState(entity_id="pc_mage", name="Vael", pools={"vitality": 20, "arcane_focus": 3})
    victim = EntityState(
        entity_id="pc_victim",
        name="Bran",
        base_properties={"might": 16, "agility": 12},
        pools={"vitality": 20, "arcane_focus": 0},
        conditions={},
        available_forms=(),
    )
    # Give victim 'warded' to verify forced=True bypasses requires="!has_condition(@self, 'warded')"
    victim = victim.model_copy(
        update={"conditions": {"warded": ActiveCondition(condition_id="warded")}}
    )
    initial = initialize_scene_state(rs, "tower", [mage, victim])
    all_events: list[VmEvent] = []

    # 1. Hostile spell opens reaction window first
    pending = execute_action(rs, initial, "pc_mage", "polymorph_hex", target_id="pc_victim")
    assert pending.status == "pending_reaction"
    assert pending.pending_window is not None
    assert pending.pending_window.prompts[0].eligible_reaction_ids == ("counter_ward",)
    all_events.extend(pending.events)

    # 2. Target declines reaction -> mage pays arcane_focus (3->2), victim forced into sheep
    cast_res = resolve_pending_reaction(
        rs, pending.state, responses=[("pc_victim", None)], timed_out=False
    )
    assert cast_res.status == "executed"
    all_events.extend(cast_res.events)

    assert cast_res.state.entities["pc_mage"].pools["arcane_focus"] == 2
    sheep_ent = cast_res.state.entities["pc_victim"]
    assert sheep_ent.pools["arcane_focus"] == 0
    assert sheep_ent.active_form is not None
    assert sheep_ent.active_form.form_id == "sheep"
    assert sheep_ent.active_form.remaining_turns == 5
    assert sheep_ent.active_form.involuntary is True
    assert sheep_ent.active_form.source_entity_id == "pc_mage"

    sheep_view = compute_entity_view(rs, sheep_ent)
    assert sheep_view.active_form_id == "sheep"
    assert sheep_view.active_form_involuntary is True
    assert sheep_view.properties["might"] == 3
    assert sheep_view.pools["vitality"] == 4

    # 3. Voluntary revert_form fails; non-forced EffectSpec is a safe no-op
    with pytest.raises(PermissionError):
        revert_form(rs, cast_res.state, "pc_victim")

    noop_release = execute_action(rs, cast_res.state, "pc_victim", "attempt_self_release")
    assert noop_release.state.entities["pc_victim"].active_form is not None
    assert noop_release.state.entities["pc_victim"].active_form.form_id == "sheep"
    all_events.extend(noop_release.events)

    # 4. Mismatched target_key on revert_form leaves active sheep form untouched
    mismatch_res = execute_action(
        rs, noop_release.state, "pc_mage", "mismatched_dispel", target_id="pc_victim"
    )
    assert mismatch_res.state.entities["pc_victim"].active_form is not None
    assert mismatch_res.state.entities["pc_victim"].active_form.form_id == "sheep"
    all_events.extend(mismatch_res.events)

    # 5. Forced targeted dispel reverts involuntary sheep form & fires on_form_reverted
    dispel_res = execute_action(
        rs, mismatch_res.state, "pc_mage", "dispel_sheep", target_id="pc_victim"
    )
    all_events.extend(dispel_res.events)
    after_dispel = dispel_res.state.entities["pc_victim"]
    assert after_dispel.active_form is None
    assert "exhausted" in after_dispel.conditions
    assert compute_entity_view(rs, after_dispel).active_form_involuntary is False

    # 6. Involuntary form also reverts cleanly via tick_active_form expiry OR form_pool_depleted
    rehex_pending = execute_action(
        rs, dispel_res.state, "pc_mage", "polymorph_hex", target_id="pc_victim"
    )
    rehex = resolve_pending_reaction(rs, rehex_pending.state, responses=[("pc_victim", None)])
    all_events.extend([*rehex_pending.events, *rehex.events])
    expired = tick_active_form(rs, rehex.state, "pc_victim", turns=5)
    assert expired.active_form is None
    assert any(
        evt.event_type == "CONDITION_CHANGED" and evt.payload.get("condition_id") == "exhausted"
        for evt in expired.events
    )
    all_events.extend(expired.events)

    third_hex = shift_into_form(
        rs,
        expired.state,
        "pc_victim",
        "sheep",
        forced=True,
        source_entity_id="pc_mage",
    )
    all_events.extend(third_hex.events)
    assert can_shift_into_form(rs, after_dispel, "sheep", forced=True) == (True, None)
    smashed = execute_action(rs, third_hex.state, "pc_mage", "smash", target_id="pc_victim")
    all_events.extend(smashed.events)
    assert any(
        evt.event_type == "CONDITION_CHANGED" and evt.payload.get("condition_id") == "exhausted"
        for evt in smashed.events
    )
    after_smash = smashed.state.entities["pc_victim"]
    assert after_smash.active_form is None
    assert after_smash.pools["vitality"] == 18

    replayed = replay_events(rs, initial, all_events)
    assert state_hash(replayed) == state_hash(smashed.state)


@pytest.mark.zero_ai
def test_event_hooks_lycanthropy_entry_exit_and_condition_break() -> None:
    """Verify broadcast scene hooks, on_form_entered/reverted, and on_condition_changed revert."""
    rs = _spell_and_hook_ruleset()
    lycan = EntityState(
        entity_id="pc_lycan",
        name="Fen",
        base_properties={"might": 11, "agility": 13},
        pools={"vitality": 20, "arcane_focus": 0},
        tags=("lycanthrope",),
    )
    villager = EntityState(
        entity_id="npc_villager",
        name="Milo",
        base_properties={"might": 10, "agility": 10},
        pools={"vitality": 12, "arcane_focus": 0},
        conditions={"hex_anchor": ActiveCondition(condition_id="hex_anchor")},
    )
    initial = initialize_scene_state(rs, "moors", [lycan, villager])
    all_events: list[VmEvent] = []

    with pytest.raises(ValueError, match="broadcast_to_entities"):
        trigger_event_hooks(
            rs,
            initial,
            event_name="on_moon_phase_changed",
            actor_id="pc_lycan",
            broadcast_to_entities=True,
        )
    with pytest.raises(KeyError):
        trigger_event_hooks(rs, initial, event_name="on_moon_phase_changed", actor_id="missing")

    # Scene-level pulse (actor_id=None): entity "self" effects safely no-op, scene clock advances
    pulsed_state, pulse_events = trigger_event_hooks(
        rs, initial, event_name="on_scene_pulse", event_data={"tick": 1}
    )
    all_events.extend(pulse_events)
    assert pulsed_state.clocks["moon_cycle"] == 1
    assert pulsed_state.entities["pc_lycan"].pools["vitality"] == 20

    # Broadcast moon phase: shifts only 'lycanthrope' tagged entity into 'werewolf' & sets frenzy
    moon_state, moon_events = trigger_event_hooks(
        rs,
        pulsed_state,
        event_name="on_moon_phase_changed",
        event_data={"phase": "full"},
        broadcast_to_entities=True,
    )
    all_events.extend(moon_events)
    lycan_after = moon_state.entities["pc_lycan"]
    assert lycan_after.active_form is not None
    assert lycan_after.active_form.form_id == "werewolf"
    assert lycan_after.active_form.involuntary is True
    assert "frenzied" in lycan_after.conditions
    assert compute_entity_view(rs, lycan_after).properties["might"] == 17
    assert moon_state.entities["npc_villager"].active_form is None

    # Forced revert on lycan fires on_form_reverted -> applies 'exhausted'
    rev_res = revert_form(rs, moon_state, "pc_lycan", forced=True, reason="silver_dawn")
    all_events.extend(rev_res.events)
    assert rev_res.state.entities["pc_lycan"].active_form is None
    assert "exhausted" in rev_res.state.entities["pc_lycan"].conditions

    # Condition-break hook: villager shifted into 'sheep', cleanse removes 'hex_anchor',
    # on_condition_changed triggers revert_form(forced=True) -> on_form_reverted ('exhausted')
    cursed = shift_into_form(
        rs, rev_res.state, "npc_villager", "sheep", forced=True, source_entity_id="pc_lycan"
    )
    all_events.extend(cursed.events)
    assert cursed.state.entities["npc_villager"].active_form is not None

    cleansed = execute_action(
        rs, cursed.state, "pc_lycan", "cleanse_curse", target_id="npc_villager"
    )
    all_events.extend(cleansed.events)
    villager_end = cleansed.state.entities["npc_villager"]
    assert "hex_anchor" not in villager_end.conditions
    assert villager_end.active_form is None
    assert "exhausted" in villager_end.conditions

    replayed = replay_events(rs, initial, all_events)
    assert state_hash(replayed) == state_hash(cleansed.state)


@pytest.mark.zero_ai
def test_form_effect_validation_and_bounded_hook_recursion() -> None:
    """Unknown form IDs fail validate_graph and cyclic on_form_entered hooks terminate cleanly."""
    bad_rs = _spell_and_hook_ruleset().model_copy(
        update={
            "event_hooks": {
                "bad_shift": EventHookBlock(
                    hook_id="bad_shift",
                    event_name="on_moon_phase_changed",
                    effects=(
                        EffectSpec(
                            kind="shift_form",
                            target_scope="self",
                            target_key="ghost_form",
                        ),
                    ),
                ),
                "bad_revert": EventHookBlock(
                    hook_id="bad_revert",
                    event_name="on_moon_phase_changed",
                    effects=(
                        EffectSpec(
                            kind="revert_form",
                            target_scope="self",
                            target_key="ghost_form",
                        ),
                    ),
                ),
            }
        }
    )
    errs = bad_rs.validate_graph()
    assert len(errs) == 2

    # Empty target_key on revert_form is valid (means revert whichever form is active)
    cyclic_rs = RulesetSchema(
        manifest=PackageManifest(
            package_type="ruleset",
            package_id="cyclic_forms",
            name="Cyclic Forms",
            version="0.1.0",
        ),
        actions={
            "safe_revert": ActionBlock(
                action_id="safe_revert",
                label="Safe Revert",
                default_effects=(EffectSpec(kind="revert_form", target_scope="self"),),
            )
        },
        forms={
            "form_a": FormBlock(form_id="form_a", label="Form A"),
            "form_b": FormBlock(form_id="form_b", label="Form B"),
        },
        event_hooks={
            "a_to_b": EventHookBlock(
                hook_id="a_to_b",
                event_name="on_form_entered",
                condition="@event.form_id == 'form_a'",
                effects=(EffectSpec(kind="shift_form", target_scope="self", target_key="form_b"),),
            ),
            "b_to_a": EventHookBlock(
                hook_id="b_to_a",
                event_name="on_form_entered",
                condition="@event.form_id == 'form_b'",
                effects=(EffectSpec(kind="shift_form", target_scope="self", target_key="form_a"),),
            ),
        },
    )
    assert cyclic_rs.validate_graph() == []

    hero = EntityState(entity_id="pc_1", name="Hero")
    initial = initialize_scene_state(cyclic_rs, "cycle_lab", [hero])
    res = shift_into_form(cyclic_rs, initial, "pc_1", "form_a")

    # Initial shift + hook depths 0..DEFAULT_MAX_HOOK_DEPTH inclusive (1 + (4 + 1) = 6)
    form_events = [evt for evt in res.events if evt.event_type == "FORM_CHANGED"]
    assert len(form_events) == 2 + DEFAULT_MAX_HOOK_DEPTH
    assert res.active_form is not None
    assert res.active_form.form_id in {"form_a", "form_b"}

    replayed = replay_events(cyclic_rs, initial, res.events)
    assert state_hash(replayed) == state_hash(res.state)
