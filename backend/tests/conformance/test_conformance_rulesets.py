"""Golden-file conformance scenarios across all 3 Showcase + 4 Minimal Ruleset Fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.ruleset_vm import (
    AdvancementGraphSpec,
    CapacityRule,
    CreationGraphSpec,
    EntityState,
    InventoryGraphState,
    ItemNode,
    PackagePickStepSpec,
    PointBuyStepSpec,
    RandomRollStepSpec,
    RulesetSchema,
    StandardArrayStepSpec,
    VmEvent,
    add_item,
    advance_turn,
    apply_event,
    apply_package_pick,
    apply_playbook_triggers,
    apply_point_buy,
    apply_standard_array,
    apply_tier_up,
    assign_rolled_attributes,
    compute_entity_view,
    execute_action,
    finalize_character,
    handoff_spotlight,
    initialize_scene_state,
    mark_skill_tick,
    replay_events,
    resolve_pending_reaction,
    resolve_skill_improvement_pass,
    roll_random_attributes,
    start_creation_session,
    start_round_initiative,
    state_hash,
)
from app.ruleset_vm.rng import SceneRngRegistry

REPO_ROOT = Path(__file__).resolve().parents[3]
SAMPLE_RULESETS_DIR = REPO_ROOT / "sample_rulesets"
PROVENANCE_PATH = REPO_ROOT / "assets" / "PROVENANCE.md"

RULESET_DIRS: tuple[tuple[str, Path], ...] = (
    ("classic_d20_fantasy", SAMPLE_RULESETS_DIR / "showcase" / "classic_d20_fantasy"),
    (
        "grimdark_d100_investigative",
        SAMPLE_RULESETS_DIR / "showcase" / "grimdark_d100_investigative",
    ),
    ("narrative_2d6_clocks", SAMPLE_RULESETS_DIR / "showcase" / "narrative_2d6_clocks"),
    ("dice_pool_successes", SAMPLE_RULESETS_DIR / "conformance" / "dice_pool_successes"),
    ("step_symbol_dice", SAMPLE_RULESETS_DIR / "conformance" / "step_symbol_dice"),
    (
        "resource_wager_card_draw",
        SAMPLE_RULESETS_DIR / "conformance" / "resource_wager_card_draw",
    ),
    ("rules_light_narrative", SAMPLE_RULESETS_DIR / "conformance" / "rules_light_narrative"),
)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _all_scenario_cases() -> list[tuple[str, Path, dict[str, Any]]]:
    cases: list[tuple[str, Path, dict[str, Any]]] = []
    for pkg_id, folder in RULESET_DIRS:
        payload = _load_json(folder / "scenarios.json")
        for scen in payload["scenarios"]:
            cases.append((pkg_id, folder, scen))
    return cases


SCENARIO_CASES = _all_scenario_cases()


def _verify_inventory_mode(mode_tag: str) -> None:
    if mode_tag == "weight_limit_ok":
        inv = InventoryGraphState(
            root_capacity=CapacityRule(mode="weight", max_weight_formula="@self.str_score * 15")
        )
        inv = add_item(
            inv,
            ItemNode(item_id="sword_1", template_id="longsword", name="Longsword", unit_weight=3.0),
            owner_ctx={"@self": {"str_score": 16}},
        )
        assert "sword_1" in inv.items
    elif mode_tag == "abstract_load_ok":
        inv = InventoryGraphState(
            root_capacity=CapacityRule(
                mode="abstract_load",
                load_tiers={"light": 3, "normal": 5, "heavy": 6},
                selected_load_tier="light",
            )
        )
        inv = add_item(
            inv,
            ItemNode(item_id="blade_1", template_id="blade", name="Blade", load_cost=2),
        )
        assert "blade_1" in inv.items
    elif mode_tag == "unlimited_ok":
        inv = InventoryGraphState(root_capacity=CapacityRule(mode="unlimited"))
        inv = add_item(
            inv,
            ItemNode(
                item_id="ancestral_blade",
                template_id="ancestral_blade",
                name="Ancestral Blade",
            ),
        )
        assert "ancestral_blade" in inv.items


@pytest.mark.zero_ai
@pytest.mark.conformance
def test_all_seven_rulesets_validate_and_have_provenance() -> None:
    """Validate all 7 bundled rulesets strictly and verify PROVENANCE.md entries."""
    assert len(RULESET_DIRS) == 7
    assert PROVENANCE_PATH.is_file()
    provenance_text = PROVENANCE_PATH.read_text(encoding="utf-8")

    for pkg_id, folder in RULESET_DIRS:
        ruleset_path = folder / "ruleset.json"
        assert ruleset_path.is_file(), f"Missing ruleset.json in {folder}"
        ruleset = RulesetSchema.model_validate(_load_json(ruleset_path))
        assert ruleset.manifest.package_id == pkg_id
        assert ruleset.validate_graph() == []
        assert pkg_id in provenance_text

        if pkg_id == "rules_light_narrative":
            assert ruleset.properties == {}
            assert ruleset.resource_pools == {}
        if pkg_id == "grimdark_d100_investigative":
            assert "resurrection_none" in ruleset.declared_primitives


@pytest.mark.zero_ai
@pytest.mark.conformance
def test_showcase_creation_and_advancement_pipelines() -> None:
    """Exercise creation + advancement schemas across all 3 Showcase Rulesets."""
    # 1. Classic d20: Point-Buy + Package Pick -> Tier 2 Level-Up
    d20_dir = SAMPLE_RULESETS_DIR / "showcase" / "classic_d20_fantasy"
    d20_rs = RulesetSchema.model_validate(_load_json(d20_dir / "ruleset.json"))
    d20_cre = CreationGraphSpec.model_validate(_load_json(d20_dir / "creation.json"))
    d20_adv = AdvancementGraphSpec.model_validate(_load_json(d20_dir / "advancement.json"))
    assert d20_adv.level_up is not None

    pb_step = next(s for s in d20_cre.steps if isinstance(s, PointBuyStepSpec))
    pkg_step = next(s for s in d20_cre.steps if isinstance(s, PackagePickStepSpec))
    sess = start_creation_session(d20_cre, d20_rs, entity_id="hero_1", name="Rowan")
    sess = apply_point_buy(
        sess,
        pb_step,
        {
            "str_score": 15,
            "dex_score": 14,
            "con_score": 14,
            "int_score": 8,
            "wis_score": 10,
            "cha_score": 8,
        },
    )
    sess = apply_package_pick(d20_rs, sess, pkg_step, "fighter")
    hero, _ = finalize_character(d20_cre, d20_rs, sess)
    hero = hero.model_copy(update={"pools": {**hero.pools, "xp": 350}})
    lvl_res = apply_tier_up(d20_rs, hero, d20_adv.level_up, 2, archetype_choice_id="battle_master")
    assert lvl_res.event.event_type == "CHARACTER_ADVANCED"
    assert "tier_2_veteran" in lvl_res.entity.tags
    assert "maneuver_dice" in lvl_res.entity.tags

    # 2. Grimdark d100: Random Roll + Occupation Package -> Usage-Driven Skill Ticks
    d100_dir = SAMPLE_RULESETS_DIR / "showcase" / "grimdark_d100_investigative"
    d100_rs = RulesetSchema.model_validate(_load_json(d100_dir / "ruleset.json"))
    d100_cre = CreationGraphSpec.model_validate(_load_json(d100_dir / "creation.json"))
    d100_adv = AdvancementGraphSpec.model_validate(_load_json(d100_dir / "advancement.json"))
    assert d100_adv.skill_ticks is not None

    roll_step = next(s for s in d100_cre.steps if isinstance(s, RandomRollStepSpec))
    occ_step = next(s for s in d100_cre.steps if isinstance(s, PackagePickStepSpec))
    d100_rng = SceneRngRegistry("d100-create-1")
    d100_sess = start_creation_session(d100_cre, d100_rs, entity_id="inv_1", name="Vesper")
    d100_sess, pool = roll_random_attributes(d100_sess, roll_step, d100_rng)
    d100_sess = assign_rolled_attributes(
        d100_sess,
        roll_step,
        {"agility_pct": pool[0], "mind_pct": pool[1], "resolve_pct": pool[2]},
    )
    d100_sess = apply_package_pick(d100_rs, d100_sess, occ_step, "private_investigator")
    inv_ent, _ = finalize_character(d100_cre, d100_rs, d100_sess)
    inv_ent = mark_skill_tick(inv_ent, "spot_hidden")
    tick_res = resolve_skill_improvement_pass(
        d100_rs, inv_ent, d100_adv.skill_ticks, ("spot_hidden",), d100_rng
    )
    assert tick_res.event.event_type == "CHARACTER_ADVANCED"
    assert "skill_tick:spot_hidden" not in tick_res.entity.tags

    # 3. Narrative 2d6: Playbook Package + Standard Array -> Playbook Triggers Clock
    n2d6_dir = SAMPLE_RULESETS_DIR / "showcase" / "narrative_2d6_clocks"
    n2d6_rs = RulesetSchema.model_validate(_load_json(n2d6_dir / "ruleset.json"))
    n2d6_cre = CreationGraphSpec.model_validate(_load_json(n2d6_dir / "creation.json"))
    n2d6_adv = AdvancementGraphSpec.model_validate(_load_json(n2d6_dir / "advancement.json"))
    assert n2d6_adv.playbook_triggers is not None

    pb_pick = next(s for s in n2d6_cre.steps if isinstance(s, PackagePickStepSpec))
    arr_step = next(s for s in n2d6_cre.steps if isinstance(s, StandardArrayStepSpec))
    n_sess = start_creation_session(n2d6_cre, n2d6_rs, entity_id="scoundrel_1", name="Corvus")
    n_sess = apply_package_pick(n2d6_rs, n_sess, pb_pick, "lurk")
    n_sess = apply_standard_array(
        n_sess, arr_step, {"prowl": 2, "finesse": 1, "sway": 1, "attune": 0}
    )
    scoundrel, _ = finalize_character(n2d6_cre, n2d6_rs, n_sess)
    trig_res = apply_playbook_triggers(
        n2d6_rs,
        scoundrel,
        n2d6_adv.playbook_triggers,
        n2d6_adv.playbook_triggers.triggers[:2],
    )
    assert trig_res.event.event_type == "CHARACTER_ADVANCED"
    assert trig_res.entity.pools["playbook_xp"] == 2


@pytest.mark.zero_ai
@pytest.mark.conformance
@pytest.mark.parametrize(
    ("pkg_id", "folder", "scenario"),
    SCENARIO_CASES,
    ids=[f"{pkg}:{scen['scenario_id']}" for pkg, _, scen in SCENARIO_CASES],
)
def test_all_fourteen_golden_scenarios_and_replay_hash(
    pkg_id: str,
    folder: Path,
    scenario: dict[str, Any],
) -> None:
    """Execute every golden scenario across all 7 rulesets & verify exact VM replay hash."""
    del pkg_id
    ruleset = RulesetSchema.model_validate(_load_json(folder / "ruleset.json"))
    entities = [EntityState.model_validate(raw) for raw in scenario["entities"]]
    initial_state = initialize_scene_state(
        ruleset,
        scenario["scene_id"],
        entities,
        scene_seed=scenario["scene_seed"],
    )
    state = initial_state
    events: list[VmEvent] = []
    rng_reg = SceneRngRegistry(scenario["scene_seed"], state.rng_streams)

    flow_start_mode = scenario.get("flow_start_mode", "freeform")
    if flow_start_mode == "round_initiative" and len(entities) >= 1:
        entity_contexts = {
            eid: compute_entity_view(ruleset, ent).to_eval_context()
            for eid, ent in state.entities.items()
        }
        next_flow = start_round_initiative(
            ruleset,
            entity_contexts,
            rng_reg.stream("initiative"),
        )
        flow_evt = VmEvent(
            event_id=f"evt_{state.scene_id}_{state.event_seq + 1:06d}",
            event_type="FLOW_UPDATED",
            payload={"flow": next_flow.model_dump(mode="json")},
        )
        events.append(flow_evt)
        state = apply_event(ruleset, state, flow_evt)

    last_roll_kind: str | None = None
    drawn_cards_all: list[str] = []

    for step in scenario["steps"]:
        kind = step["kind"]
        if kind == "action":
            res = execute_action(
                ruleset,
                state,
                step["actor_id"],
                step["action_id"],
                target_id=step.get("target_id"),
                wager_bonus=step.get("wager_bonus", 0),
                bypass_reactions=step.get("bypass_reactions", False),
            )
            assert res.status == step.get("expect_status", "executed")
            state = res.state
            events.extend(res.events)
            if res.roll_result is not None:
                last_roll_kind = res.roll_result.kind
                drawn_cards_all.extend(res.roll_result.drawn_cards)
        elif kind == "reaction":
            responses = [(r[0], r[1]) for r in step["responses"]]
            res = resolve_pending_reaction(ruleset, state, responses=responses)
            assert res.status == step.get("expect_status", "executed")
            state = res.state
            events.extend(res.events)
            if res.roll_result is not None:
                last_roll_kind = res.roll_result.kind
                drawn_cards_all.extend(res.roll_result.drawn_cards)
        elif kind == "handoff_spotlight":
            next_flow = handoff_spotlight(
                state.flow,
                step["next_actor_id"],
                list(state.entities.keys()),
            )
            evt = VmEvent(
                event_id=f"evt_{state.scene_id}_{state.event_seq + 1:06d}",
                event_type="FLOW_UPDATED",
                payload={"flow": next_flow.model_dump(mode="json")},
            )
            events.append(evt)
            state = apply_event(ruleset, state, evt)
        elif kind == "advance_turn":
            next_flow = advance_turn(state.flow)
            evt = VmEvent(
                event_id=f"evt_{state.scene_id}_{state.event_seq + 1:06d}",
                event_type="FLOW_UPDATED",
                payload={"flow": next_flow.model_dump(mode="json")},
            )
            events.append(evt)
            state = apply_event(ruleset, state, evt)

    assertions = scenario.get("assertions", {})
    for ent_id, ent_assert in assertions.get("entities", {}).items():
        ent = state.entities[ent_id]
        for pool_k, pool_v in ent_assert.get("pools", {}).items():
            assert ent.pools[pool_k] == pool_v
        for pool_k, pool_max in ent_assert.get("pool_max_check", {}).items():
            assert ent.pools[pool_k] <= pool_max
        for cond in ent_assert.get("has_conditions", []):
            assert cond in ent.conditions
        for cond in ent_assert.get("lacks_conditions", []):
            assert cond not in ent.conditions
        if "derived_properties" in ent_assert:
            view = compute_entity_view(ruleset, ent)
            for pk, pv in ent_assert["derived_properties"].items():
                assert view.properties[pk] == pv

    for clk_id, clk_v in assertions.get("clocks", {}).items():
        assert state.clocks.get(clk_id, 0) == clk_v
    for clk_id, clk_min in assertions.get("clocks_min", {}).items():
        assert state.clocks.get(clk_id, 0) >= clk_min

    if "flow_active_actor" in assertions:
        assert state.flow.active_entity_id == assertions["flow_active_actor"]

    for deck_id, expected_drawn in assertions.get("deck_unique_drawn_count", {}).items():
        assert len(drawn_cards_all) == expected_drawn
        assert len(set(drawn_cards_all)) == expected_drawn
        assert len(state.decks[deck_id].discard_pile) == expected_drawn

    for deck_id, expected_rem in assertions.get("deck_draw_pile_remaining", {}).items():
        assert len(state.decks[deck_id].draw_pile) == expected_rem

    if "expect_roll_kind" in assertions:
        assert last_roll_kind == assertions["expect_roll_kind"]

    if "log_contains" in assertions:
        assert any(assertions["log_contains"] in line for line in state.log_messages)

    if "inventory_check" in assertions:
        _verify_inventory_mode(assertions["inventory_check"])

    replayed = replay_events(ruleset, initial_state, events)
    assert state_hash(replayed) == state_hash(state)
