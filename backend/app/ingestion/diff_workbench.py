"""Interactive Staging & Diff Review Workbench API and Hot-Reload Migration Checker."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from pydantic import BaseModel, ConfigDict, Field

from app.ingestion.ai_architect import RulesetPatchSpec, apply_ruleset_patch
from app.ingestion.balance_simulator import RulesetLintReport, lint_ruleset_schema
from app.ingestion.deterministic_ingestor import (
    IngestionValidationError,
    ingest_document_deterministically,
)
from app.ingestion.lifecycle_probes import run_deterministic_probes
from app.ingestion.models import (
    BlockCategory,
    IngestionStagingJob,
    ParsedDocument,
    ProposalDecision,
    StagingBlockProposal,
)
from app.ruleset_vm import PackageManifest, RulesetSchema, SceneState, compute_entity_view


class WorkbenchCommitPreview(BaseModel):
    """Non-destructive dry-run preview of committing reviewed proposals into a RulesetSchema."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    valid: bool
    candidate_ruleset: RulesetSchema | None = None
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    lint_report: RulesetLintReport | None = None
    applied_count: int = 0
    skipped_count: int = 0
    pending_count: int = 0


class WorkbenchCommitResult(BaseModel):
    """Committed RulesetSchema & updated StagingJob produced after Diff Workbench approval."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    job: IngestionStagingJob
    ruleset: RulesetSchema
    ruleset_hash: str
    applied_proposal_ids: tuple[str, ...] = ()
    skipped_proposal_ids: tuple[str, ...] = ()


class RulesetMigrationReport(BaseModel):
    """In-campaign hot-reload compatibility report & migrated SceneState preview."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    compatible: bool
    added_properties: dict[str, object] = Field(default_factory=dict)
    removed_properties: tuple[str, ...] = ()
    added_pools: dict[str, int] = Field(default_factory=dict)
    removed_pools: tuple[str, ...] = ()
    removed_active_conditions: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    migrated_state: SceneState


_MAP_FIELD_BY_CATEGORY: dict[BlockCategory, str] = {
    "property": "properties",
    "resource_pool": "resource_pools",
    "resolution": "resolutions",
    "condition": "conditions",
    "action": "actions",
    "event_hook": "event_hooks",
    "deck": "decks",
    "form": "forms",
}


def create_staging_job_from_document(
    doc: ParsedDocument,
    *,
    existing_ruleset: RulesetSchema | None = None,
    run_probes: bool = True,
    package_id: str = "draft_ruleset",
    name: str | None = None,
) -> IngestionStagingJob:
    """Parse a document into a StagingJob with deterministic table/heuristic/probe diffs."""
    job = ingest_document_deterministically(
        doc,
        existing_ruleset=existing_ruleset,
        package_id=package_id,
        name=name,
    )
    probe_results = (
        run_deterministic_probes(doc, existing_ruleset=existing_ruleset) if run_probes else ()
    )
    if not probe_results:
        return job

    existing_keys = {(p.block_category, p.block_key) for p in job.proposals}
    merged_proposals: list[StagingBlockProposal] = list(job.proposals)
    for pr in probe_results:
        for prop in pr.proposals:
            ident = (prop.block_category, prop.block_key)
            if ident in existing_keys:
                continue
            existing_keys.add(ident)
            merged_proposals.append(prop)

    return job.model_copy(
        update={
            "proposals": tuple(merged_proposals),
            "probe_results": probe_results,
        }
    )


def create_staging_job_from_patch(
    patch: RulesetPatchSpec,
    base_ruleset: RulesetSchema,
    *,
    source_name: str = "ai_architect",
) -> IngestionStagingJob:
    """Create a reviewable Diff Workbench job from a RulesetPatchSpec."""
    res = apply_ruleset_patch(base_ruleset, patch, source_name=source_name)
    return res.staging_job


def review_proposal(
    job: IngestionStagingJob,
    proposal_id: str,
    decision: ProposalDecision,
    *,
    edited_payload: Mapping[str, object] | None = None,
    notes: str | None = None,
) -> IngestionStagingJob:
    """Apply an Accept / Merge / Edit / Skip decision to a staged proposal."""
    found = False
    updated: list[StagingBlockProposal] = []
    for prop in job.proposals:
        if prop.proposal_id != proposal_id:
            updated.append(prop)
            continue
        found = True
        next_payload = dict(prop.proposed_payload)
        if edited_payload is not None:
            if decision == "merged":
                base_map = dict(prop.existing_payload or {})
                base_map.update(edited_payload)
                next_payload = base_map
            else:
                next_payload = dict(edited_payload)
        elif decision == "merged" and prop.existing_payload is not None:
            merged_map = dict(prop.existing_payload)
            merged_map.update(prop.proposed_payload)
            next_payload = merged_map
        updated.append(
            prop.model_copy(
                update={
                    "decision": decision,
                    "proposed_payload": next_payload,
                    "notes": notes if notes is not None else prop.notes,
                }
            )
        )
    if not found:
        raise KeyError(f"Unknown proposal_id '{proposal_id}' in job '{job.job_id}'.")
    return job.model_copy(update={"proposals": tuple(updated)})


def bulk_accept_proposals(
    job: IngestionStagingJob,
    *,
    min_confidence: float = 0.85,
    exclude_conflicts: bool = True,
) -> IngestionStagingJob:
    """Accept all pending high-confidence proposals cleanly without overriding conflicts."""
    updated: list[StagingBlockProposal] = []
    for prop in job.proposals:
        if (
            prop.decision == "pending"
            and prop.confidence_score >= min_confidence
            and not (exclude_conflicts and prop.diff_status == "CONFLICT")
        ):
            updated.append(prop.model_copy(update={"decision": "accepted"}))
        else:
            updated.append(prop)
    return job.model_copy(update={"proposals": tuple(updated)})


def confirm_probe_absence(job: IngestionStagingJob, domain_id: str) -> IngestionStagingJob:
    """Confirm a Null/Absent probe domain declaration in the Staging Diff Workbench."""
    found = False
    updated = []
    for pr in job.probe_results:
        if pr.domain_id != domain_id:
            updated.append(pr)
            continue
        found = True
        updated.append(
            pr.model_copy(
                update={
                    "status": "absent",
                    "declared_value": "none",
                    "summary": f"Confirmed dormant/absent by reviewer ({pr.label}).",
                }
            )
        )
    if not found:
        raise KeyError(f"Unknown probe domain_id '{domain_id}' in job '{job.job_id}'.")
    return job.model_copy(update={"probe_results": tuple(updated)})


def preview_commit(
    job: IngestionStagingJob,
    *,
    base_ruleset: RulesetSchema | None = None,
    package_id: str = "committed_ruleset",
    name: str | None = None,
) -> WorkbenchCommitPreview:
    """Compile approved proposals onto base_ruleset (or fresh draft) and run validation lint."""
    if base_ruleset is not None:
        data = cast(dict[str, object], base_ruleset.model_dump(mode="json"))
    else:
        manifest = PackageManifest(
            package_type="ruleset",
            package_id=package_id,
            name=name or job.source_name,
            version="0.1.0",
        )
        data = cast(dict[str, object], RulesetSchema(manifest=manifest).model_dump(mode="json"))

    applied_count = 0
    skipped_count = 0
    pending_count = 0
    warnings: list[str] = list(job.warnings)

    for prop in job.proposals:
        if prop.decision == "skipped":
            skipped_count += 1
            continue
        if prop.decision == "pending":
            pending_count += 1
            continue
        if prop.decision not in {"accepted", "merged", "edited"}:
            continue

        applied_count += 1
        if prop.block_category in _MAP_FIELD_BY_CATEGORY:
            field_name = _MAP_FIELD_BY_CATEGORY[prop.block_category]
            bucket = cast(dict[str, object], dict(cast(Mapping[str, object], data[field_name])))
            if prop.proposed_payload:
                bucket[prop.block_key] = dict(prop.proposed_payload)
            else:
                bucket.pop(prop.block_key, None)
            data[field_name] = bucket
        elif prop.block_category == "covert_ops":
            data["covert_ops"] = dict(prop.proposed_payload) if prop.proposed_payload else None
        elif prop.block_category in {"flow_config", "manifest"}:
            data[prop.block_category] = dict(prop.proposed_payload)
        else:
            warnings.append(
                f"Proposal '{prop.proposal_id}' ({prop.block_category}) stored as advisory note."
            )

    try:
        candidate = RulesetSchema.model_validate(data)
    except Exception as exc:
        return WorkbenchCommitPreview(
            valid=False,
            candidate_ruleset=None,
            errors=(str(exc),),
            warnings=tuple(warnings),
            lint_report=None,
            applied_count=applied_count,
            skipped_count=skipped_count,
            pending_count=pending_count,
        )

    lint_report = lint_ruleset_schema(candidate)
    err_msgs = tuple(d.message for d in lint_report.diagnostics if d.severity == "error")
    warn_msgs = (
        *warnings,
        *(d.message for d in lint_report.diagnostics if d.severity == "warning"),
    )
    return WorkbenchCommitPreview(
        valid=lint_report.is_valid,
        candidate_ruleset=candidate,
        errors=err_msgs,
        warnings=warn_msgs,
        lint_report=lint_report,
        applied_count=applied_count,
        skipped_count=skipped_count,
        pending_count=pending_count,
    )


def commit_staging_job(
    job: IngestionStagingJob,
    *,
    base_ruleset: RulesetSchema | None = None,
    package_id: str = "committed_ruleset",
    name: str | None = None,
) -> WorkbenchCommitResult:
    """Commit approved Diff Workbench proposals into a validated RulesetSchema."""
    preview = preview_commit(
        job,
        base_ruleset=base_ruleset,
        package_id=package_id,
        name=name,
    )
    if not preview.valid or preview.candidate_ruleset is None:
        raise IngestionValidationError(preview.errors or ("Invalid ruleset staging commit.",))

    applied_ids = tuple(
        p.proposal_id for p in job.proposals if p.decision in {"accepted", "merged", "edited"}
    )
    skipped_ids = tuple(p.proposal_id for p in job.proposals if p.decision == "skipped")
    committed_job = job.model_copy(update={"status": "committed"})
    return WorkbenchCommitResult(
        job=committed_job,
        ruleset=preview.candidate_ruleset,
        ruleset_hash=preview.candidate_ruleset.content_hash(),
        applied_proposal_ids=applied_ids,
        skipped_proposal_ids=skipped_ids,
    )


def check_ruleset_migration_compatibility(
    old_ruleset: RulesetSchema,
    new_ruleset: RulesetSchema,
    scene_state: SceneState,
) -> RulesetMigrationReport:
    """Evaluate hot-reload compatibility & produce migrated SceneState with new defaults."""
    added_props: dict[str, object] = {
        pid: new_ruleset.properties[pid].default_value
        for pid in sorted(set(new_ruleset.properties) - set(old_ruleset.properties))
    }
    removed_props = tuple(sorted(set(old_ruleset.properties) - set(new_ruleset.properties)))

    added_pools: dict[str, int] = {}
    for pool_id in sorted(set(new_ruleset.resource_pools) - set(old_ruleset.resource_pools)):
        def_cur = new_ruleset.resource_pools[pool_id].default_current
        added_pools[pool_id] = def_cur if isinstance(def_cur, int) else 0
    removed_pools = tuple(sorted(set(old_ruleset.resource_pools) - set(new_ruleset.resource_pools)))

    warnings: list[str] = []
    if removed_props:
        warnings.append(f"Removed properties require migration cleanup: {', '.join(removed_props)}")
    if removed_pools:
        warnings.append(f"Removed resource pools: {', '.join(removed_pools)}")

    migrated_entities = dict(scene_state.entities)
    removed_active_conditions: dict[str, tuple[str, ...]] = {}

    for eid, ent in sorted(scene_state.entities.items()):
        next_props = {k: v for k, v in ent.base_properties.items() if k in new_ruleset.properties}
        for pid in added_props:
            if pid not in next_props and new_ruleset.properties[pid].formula is None:
                val = new_ruleset.properties[pid].default_value
                next_props[pid] = val
        next_pools = {k: v for k, v in ent.pools.items() if k in new_ruleset.resource_pools}
        for pool_id, default_int in added_pools.items():
            if pool_id not in next_pools:
                next_pools[pool_id] = default_int

        dropped_conds = tuple(
            sorted(cid for cid in ent.conditions if cid not in new_ruleset.conditions)
        )
        if dropped_conds:
            removed_active_conditions[eid] = dropped_conds
            warnings.append(
                f"Entity '{eid}' cleared removed conditions: {', '.join(dropped_conds)}"
            )
        next_conds = {k: v for k, v in ent.conditions.items() if k in new_ruleset.conditions}
        next_form = (
            ent.active_form
            if (ent.active_form is None or ent.active_form.form_id in new_ruleset.forms)
            else None
        )
        if ent.active_form is not None and next_form is None:
            warnings.append(
                f"Entity '{eid}' reverted removed active form '{ent.active_form.form_id}'."
            )
        migrated_ent = ent.model_copy(
            update={
                "base_properties": next_props,
                "pools": next_pools,
                "conditions": next_conds,
                "active_form": next_form,
            }
        )
        # Verify derived view recomputes cleanly under updated ruleset
        compute_entity_view(new_ruleset, migrated_ent)
        migrated_entities[eid] = migrated_ent

    migrated_state = scene_state.model_copy(update={"entities": migrated_entities})
    compatible = len(new_ruleset.validate_graph()) == 0
    return RulesetMigrationReport(
        compatible=compatible,
        added_properties=added_props,
        removed_properties=removed_props,
        added_pools=added_pools,
        removed_pools=removed_pools,
        removed_active_conditions=removed_active_conditions,
        warnings=tuple(warnings),
        migrated_state=migrated_state,
    )


class StagingDiffWorkbench:
    """OO facade wrapping Diff Workbench staging, review, commit & hot-reload migration."""

    @staticmethod
    def from_document(
        doc: ParsedDocument,
        *,
        existing_ruleset: RulesetSchema | None = None,
        run_probes: bool = True,
        package_id: str = "draft_ruleset",
        name: str | None = None,
    ) -> IngestionStagingJob:
        """Create a Diff Workbench staging job from a ParsedDocument."""
        return create_staging_job_from_document(
            doc,
            existing_ruleset=existing_ruleset,
            run_probes=run_probes,
            package_id=package_id,
            name=name,
        )

    @staticmethod
    def from_patch(
        patch: RulesetPatchSpec,
        base_ruleset: RulesetSchema,
        *,
        source_name: str = "ai_architect",
    ) -> IngestionStagingJob:
        """Create a Diff Workbench staging job from a RulesetPatchSpec."""
        return create_staging_job_from_patch(patch, base_ruleset, source_name=source_name)

    @staticmethod
    def review(
        job: IngestionStagingJob,
        proposal_id: str,
        decision: ProposalDecision,
        *,
        edited_payload: Mapping[str, object] | None = None,
        notes: str | None = None,
    ) -> IngestionStagingJob:
        """Apply a review decision to a proposal inside the job."""
        return review_proposal(
            job,
            proposal_id,
            decision,
            edited_payload=edited_payload,
            notes=notes,
        )

    @staticmethod
    def bulk_accept(
        job: IngestionStagingJob,
        *,
        min_confidence: float = 0.85,
        exclude_conflicts: bool = True,
    ) -> IngestionStagingJob:
        """Bulk-accept non-conflicting high-confidence proposals."""
        return bulk_accept_proposals(
            job,
            min_confidence=min_confidence,
            exclude_conflicts=exclude_conflicts,
        )

    @staticmethod
    def confirm_probe_absence(job: IngestionStagingJob, domain_id: str) -> IngestionStagingJob:
        """Confirm a Null/Absent probe domain declaration in the Diff Workbench."""
        return confirm_probe_absence(job, domain_id)

    @staticmethod
    def preview(
        job: IngestionStagingJob,
        *,
        base_ruleset: RulesetSchema | None = None,
        package_id: str = "committed_ruleset",
        name: str | None = None,
    ) -> WorkbenchCommitPreview:
        """Preview commit validity and lint diagnostics without mutating job state."""
        return preview_commit(job, base_ruleset=base_ruleset, package_id=package_id, name=name)

    @staticmethod
    def commit(
        job: IngestionStagingJob,
        *,
        base_ruleset: RulesetSchema | None = None,
        package_id: str = "committed_ruleset",
        name: str | None = None,
    ) -> WorkbenchCommitResult:
        """Commit approved proposals into a validated RulesetSchema."""
        return commit_staging_job(
            job,
            base_ruleset=base_ruleset,
            package_id=package_id,
            name=name,
        )
