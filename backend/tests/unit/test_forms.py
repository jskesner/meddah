"""Unit tests for Universal Character Transformations & Alternate Forms (ADR-0133)."""

from __future__ import annotations

import pytest

from app.ruleset_vm import (
    ActionBlock,
    EffectSpec,
    EntityState,
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
    revert_form,
    shift_into_form,
    state_hash,
    tick_active_form,
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
