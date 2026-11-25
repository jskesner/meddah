"""Unit tests for the AI Architect wizard, patterns, formula builder & Balance Simulator."""

from __future__ import annotations

import pytest

from app.ingestion import (
    SUBSYSTEM_PATTERNS,
    FormulaClause,
    PatchOperation,
    RulesetPatchSpec,
    ScopedArchitectPrompt,
    SystemWizardConfig,
    analyze_resolution_probabilities,
    apply_ruleset_patch,
    build_formula_from_clauses,
    build_scoped_block_slice_prompt,
    explain_ruleset_formula,
    inject_subsystem_pattern,
    lint_ruleset_schema,
    list_subsystem_patterns,
    run_ai_architect_request,
    run_deterministic_system_wizard,
    run_monte_carlo_simulation,
)
from app.ruleset_vm import (
    EntityState,
    evaluate_formula,
    execute_action,
    initialize_scene_state,
)

pytestmark = pytest.mark.zero_ai

ALL_PARADIGMS = (
    "roll_over",
    "roll_under",
    "tiered_2d6",
    "dice_pool",
    "step_dice",
    "card_draw",
    "coin_flip",
    "diceless",
)


@pytest.mark.parametrize("paradigm", ALL_PARADIGMS)
def test_deterministic_system_wizard_across_all_eight_paradigms(paradigm: str) -> None:
    """Every wizard paradigm builds a valid graph that executes strike cleanly via the VM."""
    config = SystemWizardConfig(
        package_id=f"wiz_{paradigm}",
        name=f"Wizard {paradigm}",
        paradigm=paradigm,  # type: ignore[arg-type]
        flow_mode="round_initiative" if paradigm == "roll_over" else "freeform",
        enable_reactions=(paradigm == "roll_over"),
        enable_forms=True,
        covert_pillars=("stealth", "disguise"),
    )
    ruleset, job = run_deterministic_system_wizard(config)
    assert ruleset.validate_graph() == []
    assert job.status == "ready_for_review"
    assert len(job.proposals) >= 5

    lint = lint_ruleset_schema(ruleset)
    assert lint.is_valid is True
    assert any(
        m.module_id == "covert_ops" and m.state == "available" for m in lint.module_readiness
    )

    attacker = EntityState(
        entity_id="pc_hero",
        name="Hero",
        base_properties={"might": 3, "agility": 2, "cognition": 1, "resolve": 2},
        pools={"vitality": 20, "focus": 6},
    )
    defender = EntityState(
        entity_id="npc_foe",
        name="Foe",
        base_properties={"might": 2, "agility": 2, "cognition": 1, "resolve": 1},
        pools={"vitality": 20, "focus": 6},
    )
    state = initialize_scene_state(ruleset, "scene_wiz", [attacker, defender], scene_seed="wiz")
    res = execute_action(
        ruleset,
        state,
        "pc_hero",
        "strike",
        target_id="npc_foe",
        bypass_reactions=True,
    )
    assert res.status == "executed"
    assert res.roll_result is not None
    assert len(res.roll_result.breakdown) > 0


def test_all_seven_subsystem_pattern_injectors_produce_valid_rulesets() -> None:
    """All 7 1-click subsystem patterns validate cleanly and populate diff proposals."""
    patterns = list_subsystem_patterns()
    assert len(patterns) == 7
    assert patterns == SUBSYSTEM_PATTERNS

    base_ruleset, _ = run_deterministic_system_wizard(
        SystemWizardConfig(package_id="base_pat", name="Base Pattern Test", paradigm="tiered_2d6")
    )

    for info in patterns:
        patched = inject_subsystem_pattern(base_ruleset, info.pattern_id)
        assert patched.validation_errors == ()
        assert patched.proposed_ruleset.validate_graph() == []
        assert len(patched.staging_job.proposals) >= 1
        assert patched.impacted_keys


def test_formula_builder_and_deterministic_explainer() -> None:
    """Visual FormulaClause compiler emits valid AST strings with deterministic explainers."""
    clauses = (
        FormulaClause(left="@self.might", operator=">=", right="10"),
        FormulaClause(left="@self.resolve", operator=">", right="1"),
    )
    expr = build_formula_from_clauses(clauses, combine_op="&&")
    ctx = {"@self": {"might": 12, "resolve": 2}}
    assert evaluate_formula(expr, ctx) is True
    explained = explain_ruleset_formula(expr, ctx)
    assert explained.value is True
    assert "@self.might" in explained.referenced_paths
    assert "AND" in explained.explanation
    assert "is at least 10" in explained.explanation


def test_scoped_block_slice_prompt_and_ai_architect_patch_compilation() -> None:
    """Tier-B Architect sends bounded block slices, handles add/modify/remove, and stages diffs."""
    ruleset, _ = run_deterministic_system_wizard(
        SystemWizardConfig(
            package_id="arch_base",
            name="Architect Base",
            paradigm="tiered_2d6",
            core_properties=("might", "agility", "cognition", "resolve", "grit", "wit"),
        )
    )
    scoped = build_scoped_block_slice_prompt(
        ruleset,
        "Modify off_balance condition and add focused condition",
        max_blocks=4,
        max_tokens=4000,
    )
    assert isinstance(scoped, ScopedArchitectPrompt)
    assert len(scoped.included_block_keys) <= 4
    assert scoped.estimated_tokens <= 4000
    assert "RULESET_SIGNATURE:" in scoped.prompt_text

    def _fake_architect(prompt: ScopedArchitectPrompt) -> RulesetPatchSpec:
        assert "off_balance" in prompt.prompt_text
        return RulesetPatchSpec(
            summary="Add focused condition, weaken off_balance, drop unused wit",
            operations=(
                PatchOperation(
                    op="add_block",
                    block_category="condition",
                    block_key="focused",
                    payload={
                        "condition_id": "focused",
                        "label": "Focused",
                        "property_modifiers": {"might": "+1"},
                    },
                ),
                PatchOperation(
                    op="modify_block",
                    block_category="condition",
                    block_key="off_balance",
                    payload={"default_duration_turns": 2},
                ),
                PatchOperation(
                    op="remove_block",
                    block_category="property",
                    block_key="wit",
                ),
            ),
        )

    result = run_ai_architect_request(
        ruleset,
        "Modify off_balance condition and add focused condition",
        llm_patch_fn=_fake_architect,
        max_blocks=4,
    )
    assert result.validation_errors == ()
    assert "focused" in result.proposed_ruleset.conditions
    assert result.proposed_ruleset.conditions["off_balance"].default_duration_turns == 2
    assert "wit" not in result.proposed_ruleset.properties
    assert len(result.staging_job.proposals) == 3

    # Invalid patch (dangling resolution_id) surfaces validation_errors instead of silent success
    bad_res = apply_ruleset_patch(
        ruleset,
        RulesetPatchSpec(
            summary="Broken action",
            operations=(
                PatchOperation(
                    op="add_block",
                    block_category="action",
                    block_key="broken_strike",
                    payload={
                        "action_id": "broken_strike",
                        "label": "Broken",
                        "resolution_id": "nonexistent_mech",
                    },
                ),
            ),
        ),
    )
    assert bad_res.validation_errors


def test_probability_analyzer_linter_and_monte_carlo_simulator() -> None:
    """Probability curve, static AST linter, and headless TTK/deadlock simulation report."""
    ruleset, _ = run_deterministic_system_wizard(
        SystemWizardConfig(package_id="sim_test", name="Sim Test", paradigm="tiered_2d6")
    )
    curve = analyze_resolution_probabilities(
        ruleset,
        "core_check",
        modifier_values=(-2, 0, 2, 4),
        samples_per_point=250,
    )
    assert len(curve.points) == 4
    means = [pt.mean_total for pt in curve.points]
    assert means == sorted(means)
    for pt in curve.points:
        assert abs(sum(pt.tier_probabilities.values()) - 1.0) < 1e-2

    # Combat simulation reaches clear TTK resolution with high stat attacker
    attacker = EntityState(
        entity_id="att",
        name="Attacker",
        base_properties={"might": 5, "agility": 2, "cognition": 1, "resolve": 2},
        pools={"vitality": 20, "focus": 6},
    )
    defender = EntityState(
        entity_id="def",
        name="Defender",
        base_properties={"might": 1, "agility": 1, "cognition": 1, "resolve": 1},
        pools={"vitality": 12, "focus": 6},
    )
    sim = run_monte_carlo_simulation(
        ruleset,
        attacker,
        defender,
        attacker_action_id="strike",
        defender_action_id="strike",
        vitality_pool_id="vitality",
        trials=40,
        max_rounds=15,
    )
    assert sim.trials_run == 40
    assert sim.attacker_win_rate > 0.5
    assert sim.avg_ttk_rounds is not None
    assert sim.avg_ttk_rounds > 0.0
    assert sim.avg_defender_pool_drain > 0.0

    # Zero-damage deadlock detection warning
    passive = inject_subsystem_pattern(ruleset, "threat_doom_clock").proposed_ruleset
    deadlock_sim = run_monte_carlo_simulation(
        passive,
        attacker,
        defender,
        attacker_action_id="tick_threat_clock",
        vitality_pool_id="vitality",
        trials=10,
        max_rounds=5,
    )
    assert deadlock_sim.stalemate_rate == 1.0
    assert any("deadlock" in w.lower() for w in deadlock_sim.deadlock_warnings)
