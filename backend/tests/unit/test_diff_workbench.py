"""Unit tests for the Interactive Staging Diff Workbench & Hot-Reload Migration Checker."""

from __future__ import annotations

import pytest

from app.ingestion import (
    PatchOperation,
    RulesetPatchSpec,
    StagingDiffWorkbench,
    SystemWizardConfig,
    check_ruleset_migration_compatibility,
    create_staging_job_from_patch,
    parse_markdown,
    run_deterministic_system_wizard,
)
from app.ruleset_vm import ActiveCondition, ActiveFormState, EntityState, initialize_scene_state

pytestmark = pytest.mark.zero_ai


def test_staging_diff_workbench_document_review_and_commit_flow() -> None:
    """Workbench loads markdown, supports probe confirm/bulk-accept/edit/skip, and commits."""
    md = """# Iron Frontier

## Properties

| prop_id | label | value_kind | default_value | formula | category | tags |
| --- | --- | --- | --- | --- | --- | --- |
| grit | Grit | int | 3 | | primary | core |

## Resource Pools

| pool_id | label | default_current | max_formula | min_value | reset_on | track_segments |
| --- | --- | --- | --- | --- | --- | --- |
| vitality | Vitality | 15 | 15 | 0 | rest | |

## Resolutions

| mech_id | label | randomizer_kind | formula | modifier_formula | target_formula |
| --- | --- | --- | --- | --- | --- |
| duel_roll | Duel Roll | dice_formula | 2d6 | @self.grit | 8 |

## Actions

| action_id | label | category | resolution_id | requires | pool_costs | requires_target | tags |
| --- | --- | --- | --- | --- | --- | --- | --- |
| quick_draw | Quick Draw | action | duel_roll | | | true | combat |
"""
    doc = parse_markdown(md, source_name="frontier.md")
    job = StagingDiffWorkbench.from_document(doc, package_id="iron_frontier")
    assert len(job.probe_results) == 14
    assert len(job.proposals) >= 4

    # Bulk accept high confidence, confirm an absent domain explicitly, skip covert if proposed
    job = StagingDiffWorkbench.bulk_accept(job, min_confidence=0.8)
    job = StagingDiffWorkbench.confirm_probe_absence(job, "holdings_and_warfare")
    holdings_probe = next(p for p in job.probe_results if p.domain_id == "holdings_and_warfare")
    assert holdings_probe.status == "absent"
    assert holdings_probe.declared_value == "none"

    prop_grit = next(p for p in job.proposals if p.block_key == "grit")
    job = StagingDiffWorkbench.review(
        job,
        prop_grit.proposal_id,
        "edited",
        edited_payload={**prop_grit.proposed_payload, "default_value": 5},
        notes="Raised starting Grit.",
    )

    preview = StagingDiffWorkbench.preview(job, package_id="iron_frontier")
    assert preview.valid is True
    assert preview.candidate_ruleset is not None
    assert preview.candidate_ruleset.properties["grit"].default_value == 5

    committed = StagingDiffWorkbench.commit(job, package_id="iron_frontier")
    assert committed.job.status == "committed"
    assert committed.ruleset_hash == committed.ruleset.content_hash()
    assert committed.ruleset.properties["grit"].default_value == 5


def test_workbench_from_patch_rejects_broken_graph_until_edited_or_skipped() -> None:
    """Workbench preview blocks committing invalid proposals until repaired or skipped."""
    base_ruleset, _ = run_deterministic_system_wizard(
        SystemWizardConfig(package_id="wb_patch", name="WB Patch", paradigm="roll_over")
    )
    patch = RulesetPatchSpec(
        summary="Add condition + bad action",
        operations=(
            PatchOperation(
                op="add_block",
                block_category="condition",
                block_key="anchored",
                payload={"condition_id": "anchored", "label": "Anchored"},
            ),
            PatchOperation(
                op="add_block",
                block_category="action",
                block_key="ghost_strike",
                payload={
                    "action_id": "ghost_strike",
                    "label": "Ghost Strike",
                    "resolution_id": "missing_mech",
                },
            ),
        ),
    )
    job = create_staging_job_from_patch(patch, base_ruleset)
    job = StagingDiffWorkbench.bulk_accept(job, min_confidence=0.5)

    bad_preview = StagingDiffWorkbench.preview(job, base_ruleset=base_ruleset)
    assert bad_preview.valid is False
    assert bad_preview.errors

    bad_action_prop = next(p for p in job.proposals if p.block_key == "ghost_strike")
    repaired_job = StagingDiffWorkbench.review(job, bad_action_prop.proposal_id, "skipped")
    committed = StagingDiffWorkbench.commit(repaired_job, base_ruleset=base_ruleset)
    assert "anchored" in committed.ruleset.conditions
    assert "ghost_strike" not in committed.ruleset.actions


def test_hot_reload_ruleset_migration_compatibility_checker() -> None:
    """Hot-reload checker injects added defaults/pools and cleans dropped conditions/forms."""
    old_ruleset, _ = run_deterministic_system_wizard(
        SystemWizardConfig(
            package_id="mig_v1",
            name="Migration v1",
            paradigm="tiered_2d6",
            core_properties=("might", "agility"),
            enable_forms=True,
        )
    )
    new_ruleset, _ = run_deterministic_system_wizard(
        SystemWizardConfig(
            package_id="mig_v2",
            name="Migration v2",
            paradigm="tiered_2d6",
            core_properties=("might", "honor"),
            secondary_pool_id="resolve_pool",
            enable_forms=False,
        )
    )
    pc = EntityState(
        entity_id="pc_1",
        name="Scout",
        base_properties={"might": 3, "agility": 2},
        pools={"vitality": 18, "focus": 4},
        conditions={"off_balance": ActiveCondition(condition_id="off_balance", remaining_turns=2)},
        active_form=ActiveFormState(form_id="feral_aspect", remaining_turns=3),
    )
    scene = initialize_scene_state(old_ruleset, "camp_scene", [pc], scene_seed="mig")

    # Remove off_balance from new_ruleset to verify condition cleanup too
    v2_no_cond = new_ruleset.model_copy(update={"conditions": {}})
    report = check_ruleset_migration_compatibility(old_ruleset, v2_no_cond, scene)
    assert "honor" in report.added_properties
    assert "agility" in report.removed_properties
    assert "resolve_pool" in report.added_pools
    assert "focus" in report.removed_pools
    assert report.removed_active_conditions == {"pc_1": ("off_balance",)}
    assert report.warnings

    migrated_pc = report.migrated_state.entities["pc_1"]
    assert "honor" in migrated_pc.base_properties
    assert "agility" not in migrated_pc.base_properties
    assert "resolve_pool" in migrated_pc.pools
    assert migrated_pc.active_form is None
    assert migrated_pc.conditions == {}
