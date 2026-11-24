"""Unit tests for all 5 Creation Node Primitives and all 5 Progression Paradigms."""

from __future__ import annotations

import pytest

from app.ruleset_vm import (
    ArchetypeOption,
    CreationGraphSpec,
    DiegeticTrainingParadigmSpec,
    EntityState,
    LevelTierGrant,
    LevelUpParadigmSpec,
    LifepathCareerSpec,
    LifepathChainStepSpec,
    LifepathEventEntry,
    PackageManifest,
    PackageOptionSpec,
    PackagePickStepSpec,
    PlaybookTriggersParadigmSpec,
    PointBuyStepSpec,
    PropertyBlock,
    RandomizerSpec,
    RandomRollStepSpec,
    ResourcePoolBlock,
    RulesetSchema,
    SkillTicksParadigmSpec,
    StandardArrayStepSpec,
    SubChoiceOption,
    SubChoiceSpec,
    TrainingTechniqueSpec,
    XpStoreEntry,
    XpStoreParadigmSpec,
    apply_package_pick,
    apply_playbook_triggers,
    apply_point_buy,
    apply_standard_array,
    apply_tier_up,
    assign_rolled_attributes,
    check_tier_up_eligible,
    complete_diegetic_training,
    finalize_character,
    initialize_scene_state,
    mark_skill_tick,
    muster_out_lifepath,
    purchase_xp_store_item,
    replay_events,
    resolve_skill_improvement_pass,
    roll_random_attributes,
    start_creation_session,
    state_hash,
    step_lifepath_term,
)
from app.ruleset_vm.rng import SceneRngRegistry


def _creation_test_ruleset() -> RulesetSchema:
    return RulesetSchema(
        manifest=PackageManifest(
            package_type="ruleset",
            package_id="creation_test",
            name="Creation & Advancement Suite",
            version="0.1.0",
        ),
        properties={
            "brawn": PropertyBlock(prop_id="brawn", label="Brawn", default_value=10),
            "agility": PropertyBlock(prop_id="agility", label="Agility", default_value=10),
            "wit": PropertyBlock(prop_id="wit", label="Wit", default_value=10),
            "resolve": PropertyBlock(prop_id="resolve", label="Resolve", default_value=10),
            "agility_mod": PropertyBlock(
                prop_id="agility_mod",
                label="Agility Mod",
                formula="floor((@self.agility - 10) / 2)",
            ),
            "vitality_max": PropertyBlock(
                prop_id="vitality_max",
                label="Vitality Max",
                formula="10 + @self.brawn",
            ),
            "investigation": PropertyBlock(
                prop_id="investigation",
                label="Investigation",
                default_value=25,
            ),
            "stealth": PropertyBlock(prop_id="stealth", label="Stealth", default_value=0),
            "tier": PropertyBlock(prop_id="tier", label="Tier", default_value=1),
        },
        resource_pools={
            "xp": ResourcePoolBlock(pool_id="xp", label="XP", default_current=0),
            "vitality": ResourcePoolBlock(pool_id="vitality", label="Vitality", default_current=20),
            "currency": ResourcePoolBlock(
                pool_id="currency", label="Currency", default_current=100
            ),
            "playbook_xp": ResourcePoolBlock(
                pool_id="playbook_xp", label="Playbook XP", default_current=0
            ),
        },
    )


@pytest.mark.zero_ai
def test_creation_point_buy_standard_array_and_packages() -> None:
    """Point-buy cost tables, standard array validation, and gated package picks work end to end."""
    rs = _creation_test_ruleset()
    pb_step = PointBuyStepSpec(
        step_id="attrs_pb",
        label="Point Buy",
        target_properties=("brawn", "agility"),
        budget_points=10,
        min_score=8,
        max_score=15,
        cost_table={8: 0, 10: 2, 12: 4, 14: 7, 15: 9},
    )
    pkg_step = PackagePickStepSpec(
        step_id="pick_arch",
        label="Archetype",
        options=(
            PackageOptionSpec(
                option_id="warden",
                label="Warden",
                requires="@self.brawn >= 12",
                property_bonuses={"wit": 2},
                granted_tags=("martial",),
                sub_choices=(
                    SubChoiceSpec(
                        choice_id="craft",
                        label="Choose Discipline",
                        pick_count=1,
                        options=(
                            SubChoiceOption(
                                option_id="shieldwall",
                                label="Shieldwall",
                                granted_actions=("raise_guard",),
                            ),
                            SubChoiceOption(
                                option_id="ambush",
                                label="Ambush",
                                property_bonuses={"stealth": 2},
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )

    graph = CreationGraphSpec(steps=(pb_step, pkg_step), starting_pools={"xp": 350, "vitality": 20})
    session = start_creation_session(graph, rs, entity_id="hero_1", name="Tamsin")

    # Exceeding budget raises ValueError
    with pytest.raises(ValueError, match="exceeds budget"):
        apply_point_buy(session, pb_step, {"brawn": 15, "agility": 15})

    session = apply_point_buy(session, pb_step, {"brawn": 14, "agility": 10})
    session = apply_package_pick(
        rs,
        session,
        pkg_step,
        "warden",
        sub_selections={"craft": ["shieldwall"]},
    )
    entity, view = finalize_character(graph, rs, session)
    assert view.properties["brawn"] == 14
    assert view.properties["vitality_max"] == 24
    assert view.properties["wit"] == 12
    assert "martial" in entity.tags
    assert "raise_guard" in entity.granted_actions

    # Standard array validation
    arr_step = StandardArrayStepSpec(
        step_id="arr",
        label="Array",
        target_properties=("brawn", "agility", "wit"),
        array_values=(15, 12, 8),
    )
    with pytest.raises(ValueError, match="do not match"):
        apply_standard_array(session, arr_step, {"brawn": 15, "agility": 15, "wit": 8})
    arr_done = apply_standard_array(session, arr_step, {"brawn": 8, "agility": 15, "wit": 12})
    assert arr_done.base_properties["agility"] == 15


@pytest.mark.zero_ai
def test_creation_random_rolls_and_lifepath_chains() -> None:
    """Random roll pools and multi-term lifepath careers run deterministically via RNG stream."""
    rs = _creation_test_ruleset()
    roll_step = RandomRollStepSpec(
        step_id="roll_attrs",
        label="Roll Attributes",
        target_properties=("brawn", "agility", "wit"),
        roll_spec=RandomizerSpec(kind="dice_formula", formula="4d6kh3"),
        assign_mode="pool_assign",
        min_total_mercy=24,
    )
    life_step = LifepathChainStepSpec(
        step_id="career",
        label="Career History",
        careers=(
            LifepathCareerSpec(
                career_id="navigators",
                label="Void Navigators",
                requires="@self.wit >= 3",
                survival_roll=RandomizerSpec(kind="dice_formula", formula="2d6"),
                survival_target=5,
                promotion_roll=RandomizerSpec(kind="dice_formula", formula="2d6"),
                promotion_target=6,
                term_property_bonuses={"wit": 1},
                events=(
                    LifepathEventEntry(
                        event_id="charter_commendation",
                        label="Charted Deep Rift",
                        granted_tags=("rift_veteran",),
                    ),
                ),
                mustering_currency_per_term=250,
                mustering_tags=("former_navigator",),
            ),
        ),
    )

    graph = CreationGraphSpec(steps=(roll_step, life_step))
    session = start_creation_session(graph, rs, entity_id="voyager_1", name="Kestrel")
    rng_reg = SceneRngRegistry("creation-seed-7")

    session, pool = roll_random_attributes(session, roll_step, rng_reg)
    assert len(pool) == 3
    assert sum(pool) >= 24

    session = assign_rolled_attributes(
        session,
        roll_step,
        {"brawn": pool[0], "agility": pool[1], "wit": pool[2]},
    )

    session, term_1 = step_lifepath_term(rs, session, life_step, "navigators", rng_reg)
    session, _term_2 = step_lifepath_term(rs, session, life_step, "navigators", rng_reg)
    assert term_1.term_number == 1
    assert session.lifepath_terms == 2

    session = muster_out_lifepath(session, life_step, "navigators")
    entity, _ = finalize_character(graph, rs, session)
    assert entity.pools["currency"] == 600
    assert "former_navigator" in entity.tags
    assert "rift_veteran" in entity.tags


@pytest.mark.zero_ai
def test_all_five_advancement_paradigms_and_replay() -> None:
    """All 5 progression paradigms produce Before/After diffs and deterministic VM replay."""
    rs = _creation_test_ruleset()
    base_ent = EntityState(
        entity_id="pc_adv",
        name="Sora",
        base_properties={"brawn": 12, "agility": 14, "stealth": 2, "investigation": 30, "tier": 1},
        pools={"xp": 350, "vitality": 22, "currency": 400, "playbook_xp": 6},
    )
    scene_0 = initialize_scene_state(rs, "adv_scene", [base_ent], scene_seed="adv-seed")

    # 1. Level-Up / Tier Graph (with multiclass prerequisite check)
    level_spec = LevelUpParadigmSpec(
        tiers=(
            LevelTierGrant(
                tier=2,
                xp_required=300,
                property_bonuses={"agility": 2},
                pool_max_bonuses={"vitality": 5},
                granted_actions=("second_effort",),
            ),
        ),
        archetype_options=(
            ArchetypeOption(
                option_id="mystic_initiate",
                label="Mystic Initiate",
                requires="@self.agility >= 14",
                granted_tags=("mystic",),
            ),
        ),
    )
    assert check_tier_up_eligible(base_ent, level_spec) == 2
    tier_res = apply_tier_up(
        rs,
        base_ent,
        level_spec,
        target_tier=2,
        archetype_choice_id="mystic_initiate",
        scene_id="adv_scene",
        event_seq=scene_0.event_seq,
    )
    assert tier_res.diff.property_changes["agility_mod"].before == 2
    assert tier_res.diff.property_changes["agility_mod"].after == 3
    assert "second_effort" in tier_res.diff.added_actions

    # 2. Classless XP / Karma Store
    xp_store = XpStoreParadigmSpec(
        entries={
            "raise_stealth": XpStoreEntry(
                entry_id="raise_stealth",
                label="Raise Stealth",
                cost_formula="(@self.stealth + 1) * 5",
                max_rank=5,
                target_property="stealth",
                property_step=1,
            )
        }
    )
    xp_res = purchase_xp_store_item(rs, tier_res.entity, xp_store, "raise_stealth")
    assert xp_res.entity.base_properties["stealth"] == 3
    assert xp_res.diff.cost_spent == {"xp": 15}

    # 3. Usage-Driven Skill Ticks & Improvement Roll Pass
    ticked = mark_skill_tick(xp_res.entity, "investigation")
    assert "skill_tick:investigation" in ticked.tags
    ticks_spec = SkillTicksParadigmSpec(
        check_roll=RandomizerSpec(kind="dice_formula", formula="1d100"),
        gain_roll=RandomizerSpec(kind="dice_formula", formula="1d10"),
        max_skill_value=99,
    )
    ticks_res = resolve_skill_improvement_pass(
        rs,
        ticked,
        ticks_spec,
        ["investigation"],
        SceneRngRegistry("skill-pass-1"),
    )
    assert "skill_tick:investigation" not in ticks_res.entity.tags

    # 4. Playbook Triggers & Clock Wrap
    pb_spec = PlaybookTriggersParadigmSpec(
        triggers=("challenged_faction", "revealed_secret"),
        advancement_threshold=8,
    )
    pb_res = apply_playbook_triggers(
        rs,
        ticks_res.entity,
        pb_spec,
        answered_triggers=["challenged_faction", "revealed_secret"],
        chosen_upgrade=XpStoreEntry(
            entry_id="special_edge",
            label="Infiltrator Edge",
            granted_tags=("infiltrator",),
        ),
    )
    assert pb_res.entity.pools["playbook_xp"] == 0
    assert "infiltrator" in pb_res.entity.tags

    # 5. Diegetic In-World Training
    train_spec = DiegeticTrainingParadigmSpec(
        techniques={
            "master_parry": TrainingTechniqueSpec(
                technique_id="master_parry",
                label="Master Parry",
                required_trainer_tag="swordmaster",
                required_facility_tag="dojo",
                required_downtime_ticks=4,
                currency_cost=150,
                granted_actions=("riposte",),
            )
        }
    )
    with pytest.raises(PermissionError, match="trainer tag"):
        complete_diegetic_training(
            rs,
            pb_res.entity,
            train_spec,
            "master_parry",
            available_context_tags=["dojo"],
            downtime_ticks_logged=4,
        )

    train_res = complete_diegetic_training(
        rs,
        pb_res.entity,
        train_spec,
        "master_parry",
        available_context_tags=["swordmaster", "dojo"],
        downtime_ticks_logged=4,
    )
    assert "riposte" in train_res.entity.granted_actions
    assert train_res.entity.pools["currency"] == 250

    # Verify CHARACTER_ADVANCED events replay deterministically through replay_events
    replayed = replay_events(rs, scene_0, [tier_res.event])
    direct = scene_0.model_copy(
        update={
            "entities": {"pc_adv": tier_res.entity},
            "event_seq": scene_0.event_seq + 1,
        }
    )
    assert state_hash(replayed) == state_hash(direct)
