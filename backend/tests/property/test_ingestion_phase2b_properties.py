"""Hypothesis property tests for Phase 2B probes, wizard graphs & probability curves."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.ingestion import (
    SystemWizardConfig,
    analyze_resolution_probabilities,
    parse_markdown,
    run_deterministic_probes,
    run_deterministic_system_wizard,
)

pytestmark = pytest.mark.zero_ai

PARADIGM_ST = st.sampled_from(
    [
        "roll_over",
        "roll_under",
        "tiered_2d6",
        "dice_pool",
        "step_dice",
        "card_draw",
        "coin_flip",
        "diceless",
    ]
)
FLOW_ST = st.sampled_from(["freeform", "round_initiative", "popcorn_spotlight"])
CREATION_ST = st.sampled_from(
    ["point_buy", "standard_array", "random_roll", "package_pick", "lifepath"]
)
PILLAR_ST = st.lists(st.sampled_from(["stealth", "theft", "disguise"]), unique=True, max_size=3)


@given(
    filler=st.text(
        alphabet=st.sampled_from(list("bcdfgjkmnpqvwyz 0123456789\n.,")),
        min_size=1,
        max_size=120,
    )
)
@settings(max_examples=25)
def test_probes_never_invent_domains_on_neutral_consonant_text(filler: str) -> None:
    """Property: arbitrary non-domain filler never triggers false 'found' discoveries."""
    doc = parse_markdown(f"# Ledger\n\n{filler}\n", source_name="filler.md")
    results = run_deterministic_probes(doc)
    assert len(results) == 14
    assert all(res.status == "absent" and res.declared_value == "none" for res in results)


@given(
    paradigm=PARADIGM_ST,
    flow_mode=FLOW_ST,
    creation=CREATION_ST,
    enable_reactions=st.booleans(),
    enable_forms=st.booleans(),
    pillars=PILLAR_ST,
)
@settings(max_examples=30)
def test_system_wizard_always_builds_valid_ruleset_graph(
    paradigm: str,
    flow_mode: str,
    creation: str,
    enable_reactions: bool,
    enable_forms: bool,
    pillars: list[str],
) -> None:
    """Property: all combinations of wizard configuration validate cleanly."""
    config = SystemWizardConfig(
        package_id=f"prop_{paradigm}_{flow_mode}",
        name="Property Wizard",
        paradigm=paradigm,  # type: ignore[arg-type]
        flow_mode=flow_mode,  # type: ignore[arg-type]
        creation_paradigm=creation,  # type: ignore[arg-type]
        enable_reactions=enable_reactions,
        enable_forms=enable_forms,
        covert_pillars=tuple(pillars),  # type: ignore[arg-type]
    )
    ruleset, _ = run_deterministic_system_wizard(config)
    assert ruleset.validate_graph() == []


@given(
    mod=st.integers(min_value=-3, max_value=6),
    seed=st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789", min_size=1, max_size=12),
)
@settings(max_examples=20)
def test_probability_analyzer_tier_probabilities_sum_to_one(mod: int, seed: str) -> None:
    """Property: empirical tier probabilities sum to 1.0 under arbitrary modifiers & seeds."""
    ruleset, _ = run_deterministic_system_wizard(
        SystemWizardConfig(package_id="prob_prop", name="Prob Prop", paradigm="tiered_2d6")
    )
    report = analyze_resolution_probabilities(
        ruleset,
        "core_check",
        modifier_values=(mod,),
        samples_per_point=80,
        seed=seed,
    )
    assert len(report.points) == 1
    total_prob = sum(report.points[0].tier_probabilities.values())
    assert abs(total_prob - 1.0) < 1e-2
