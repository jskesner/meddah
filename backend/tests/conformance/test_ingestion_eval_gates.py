"""Dual-Track Phase 2 Ingestion Evaluation Conformance Tests (§4 Track 1 & Track 2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.ingestion import (
    TierBGoldExpectation,
    TierBMicroProbeRequest,
    evaluate_tier_a_gold_corpus,
    evaluate_tier_b_extraction,
    parse_markdown,
)

pytestmark = pytest.mark.zero_ai

REPO_ROOT = Path(__file__).resolve().parents[3]
SAMPLE_RULESETS_DIR = REPO_ROOT / "sample_rulesets"

SEVEN_RULESET_PATHS: tuple[Path, ...] = (
    SAMPLE_RULESETS_DIR / "showcase" / "classic_d20_fantasy" / "ruleset.json",
    SAMPLE_RULESETS_DIR / "showcase" / "grimdark_d100_investigative" / "ruleset.json",
    SAMPLE_RULESETS_DIR / "showcase" / "narrative_2d6_clocks" / "ruleset.json",
    SAMPLE_RULESETS_DIR / "conformance" / "dice_pool_successes" / "ruleset.json",
    SAMPLE_RULESETS_DIR / "conformance" / "step_symbol_dice" / "ruleset.json",
    SAMPLE_RULESETS_DIR / "conformance" / "resource_wager_card_draw" / "ruleset.json",
    SAMPLE_RULESETS_DIR / "conformance" / "rules_light_narrative" / "ruleset.json",
)


@pytest.mark.conformance
def test_track_1_tier_a_gold_corpus_seven_fixtures_roundtrip_and_probes() -> None:
    """Track 1: all 7 fixtures import cleanly, round-trip Markdown tables, and invent 0 domains."""
    report = evaluate_tier_a_gold_corpus(SEVEN_RULESET_PATHS)
    assert report.total_fixtures == 7
    assert report.passed_fixtures == 7, [
        (s.package_id, s.errors, s.invented_domains) for s in report.fixture_scores
    ]
    assert report.pass_rate == 1.0
    assert report.all_passed is True


@pytest.mark.conformance
@pytest.mark.tier_b_eval
def test_track_2_tier_b_eval_accuracy_zero_inventions_and_checkpoint_parity() -> None:
    """Track 2: local micro-probe harness achieves >=90% accuracy, 0 inventions, <=8192 tokens."""
    md = """# Neon Syndicate Field Manual

## Vitality & Injury
Damage drains agent vitality; suffering lethal injury inflicts the bleeding condition.

## Covert Stealth Protocols
Operators enter stealth using shadows and cover, staying hidden from patrol cones.

## Disguise & Alias Covers
Social infiltrators wear a forged alias disguise to slip past corporate checkpoints.
"""
    doc = parse_markdown(md, source_name="neon_syndicate.md")
    expectation = TierBGoldExpectation(
        doc_id=doc.doc_id,
        expected_present_domains=(
            "vitality_and_death",
            "capabilities_forms_covert",
            "social_morale_disguise",
        ),
        expected_absent_domains=(
            "vehicles_and_ontology",
            "holdings_and_warfare",
            "retinue_and_companions",
        ),
    )

    def _deterministic_micro_probe(req: TierBMicroProbeRequest) -> dict[str, object]:
        if req.domain_id in expectation.expected_present_domains:
            return {
                "probe_number": req.probe_number,
                "domain_id": req.domain_id,
                "label": req.label,
                "status": "found",
                "declared_value": "explicit_rulebook_entry",
                "confidence_score": 0.92,
                "summary": "Detected explicitly in chunk.",
            }
        return {
            "probe_number": req.probe_number,
            "domain_id": req.domain_id,
            "label": req.label,
            "status": "absent",
            "declared_value": "none",
            "confidence_score": 0.0,
            "summary": "No mechanics present.",
        }

    report = evaluate_tier_b_extraction(doc, expectation, micro_probe_fn=_deterministic_micro_probe)
    assert report.passed is True
    assert report.core_mechanics_accuracy >= 0.90
    assert report.false_positive_invented_domains == ()
    assert report.max_prompt_tokens_used <= 8192
    assert report.checkpoint_resume_identical is True
