"""Dual-Track Phase 2 Ingestion Evaluation Harness (Tier A Gold Corpus & Tier B Local Gate)."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from app.ingestion.deterministic_ingestor import (
    IngestionValidationError,
    import_ruleset_file,
    import_structured_tables,
)
from app.ingestion.document_parser import DocumentParseError, parse_markdown
from app.ingestion.lifecycle_probes import (
    TierBMicroProbeRequest,
    run_ruleset_schema_probes,
    run_tier_b_micro_probes,
)
from app.ingestion.models import ParsedDocument, ProbeDomainResult
from app.ruleset_vm import RulesetSchema


class FixtureEvalScore(BaseModel):
    """Track-1 deterministic evaluation metrics for one gold .rpgrules fixture."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    package_id: str
    json_import_ok: bool
    markdown_roundtrip_ok: bool
    probe_absent_accuracy: float = Field(ge=0.0, le=1.0)
    invented_domains: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


class TierAEvalReport(BaseModel):
    """Summary evaluation report across all 7 Tier-A conformance/showcase gold fixtures."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    total_fixtures: int
    passed_fixtures: int
    pass_rate: float = Field(ge=0.0, le=1.0)
    fixture_scores: tuple[FixtureEvalScore, ...] = ()
    all_passed: bool


class TierBGoldExpectation(BaseModel):
    """Expected present/absent domains and key blocks for Tier-B rulebook extraction."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    doc_id: str = Field(min_length=1)
    expected_present_domains: tuple[str, ...] = ()
    expected_absent_domains: tuple[str, ...] = ()
    expected_block_keys: tuple[str, ...] = ()


class TierBEvalReport(BaseModel):
    """Track-2 evaluation report enforcing >=90% accuracy, 0 inventions & checkpoint parity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    doc_id: str
    core_mechanics_accuracy: float = Field(ge=0.0, le=1.0)
    false_positive_invented_domains: tuple[str, ...] = ()
    max_prompt_tokens_used: int = Field(ge=0)
    checkpoint_resume_identical: bool
    passed: bool


def _escape_cell(raw: object) -> str:
    if raw is None:
        return ""
    return str(raw).replace("\n", " ").replace("|", "/").strip()


def _fmt_kv(mapping: Mapping[str, object]) -> str:
    if not mapping:
        return ""
    return "; ".join(f"{k}={v}" for k, v in sorted(mapping.items()))


def render_ruleset_as_markdown_tables(ruleset: RulesetSchema) -> str:
    """Render a RulesetSchema into canonical Markdown tables for deterministic import."""
    lines: list[str] = [f"# {ruleset.manifest.name}", ""]

    if ruleset.properties:
        lines.extend(
            [
                "## Properties",
                "",
                "| prop_id | label | value_kind | default_value | formula | category | tags |",
                "| --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for pid, p in sorted(ruleset.properties.items()):
            lines.append(
                "| "
                + " | ".join(
                    [
                        _escape_cell(pid),
                        _escape_cell(p.label),
                        _escape_cell(p.value_kind),
                        _escape_cell(p.default_value),
                        _escape_cell(p.formula),
                        _escape_cell(p.category),
                        _escape_cell(", ".join(p.tags)),
                    ]
                )
                + " |"
            )
        lines.append("")

    if ruleset.resource_pools:
        pool_hdr = (
            "| pool_id | label | default_current | max_formula | "
            "min_value | reset_on | track_segments |"
        )
        lines.extend(
            [
                "## Resource Pools",
                "",
                pool_hdr,
                "| --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for pool_id, pool in sorted(ruleset.resource_pools.items()):
            lines.append(
                "| "
                + " | ".join(
                    [
                        _escape_cell(pool_id),
                        _escape_cell(pool.label),
                        _escape_cell(pool.default_current),
                        _escape_cell(pool.max_formula),
                        _escape_cell(pool.min_value),
                        _escape_cell(pool.reset_on),
                        _escape_cell(pool.track_segments),
                    ]
                )
                + " |"
            )
        lines.append("")

    if ruleset.resolutions:
        res_hdr = (
            "| mech_id | label | randomizer_kind | formula | modifier_formula | target_formula |"
        )
        lines.extend(
            [
                "## Resolutions",
                "",
                res_hdr,
                "| --- | --- | --- | --- | --- | --- |",
            ]
        )
        for mid, mech in sorted(ruleset.resolutions.items()):
            r_kind = "none" if mech.randomizer.kind == "card_deck" else mech.randomizer.kind
            lines.append(
                "| "
                + " | ".join(
                    [
                        _escape_cell(mid),
                        _escape_cell(mech.label),
                        _escape_cell(r_kind),
                        _escape_cell(mech.randomizer.formula),
                        _escape_cell(mech.modifier_formula),
                        _escape_cell(mech.target_formula),
                    ]
                )
                + " |"
            )
        lines.append("")

    if ruleset.conditions:
        cond_hdr = (
            "| condition_id | label | description | property_modifiers | "
            "blocks_tags | default_duration_turns |"
        )
        lines.extend(
            [
                "## Conditions",
                "",
                cond_hdr,
                "| --- | --- | --- | --- | --- | --- |",
            ]
        )
        for cid, cond in sorted(ruleset.conditions.items()):
            lines.append(
                "| "
                + " | ".join(
                    [
                        _escape_cell(cid),
                        _escape_cell(cond.label),
                        _escape_cell(cond.description),
                        _escape_cell(_fmt_kv(cond.property_modifiers)),
                        _escape_cell(", ".join(cond.blocks_tags)),
                        _escape_cell(cond.default_duration_turns),
                    ]
                )
                + " |"
            )
        lines.append("")

    if ruleset.actions:
        act_hdr = (
            "| action_id | label | category | resolution_id | requires | "
            "pool_costs | requires_target | tags |"
        )
        lines.extend(
            [
                "## Actions",
                "",
                act_hdr,
                "| --- | --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for aid, act in sorted(ruleset.actions.items()):
            lines.append(
                "| "
                + " | ".join(
                    [
                        _escape_cell(aid),
                        _escape_cell(act.label),
                        _escape_cell(act.category),
                        _escape_cell(act.resolution_id),
                        _escape_cell(act.requires),
                        _escape_cell(_fmt_kv(act.pool_costs)),
                        _escape_cell(str(act.requires_target).lower()),
                        _escape_cell(", ".join(act.tags)),
                    ]
                )
                + " |"
            )
        lines.append("")

    if ruleset.forms:
        form_hdr = (
            "| form_id | label | description | property_mode | property_values | "
            "property_deltas | granted_tags | blocked_tags | gear_handling | "
            "default_duration_turns |"
        )
        lines.extend(
            [
                "## Forms",
                "",
                form_hdr,
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for fid, form in sorted(ruleset.forms.items()):
            lines.append(
                "| "
                + " | ".join(
                    [
                        _escape_cell(fid),
                        _escape_cell(form.label),
                        _escape_cell(form.description),
                        _escape_cell(form.property_mode),
                        _escape_cell(_fmt_kv(form.property_values)),
                        _escape_cell(_fmt_kv(form.property_deltas)),
                        _escape_cell(", ".join(form.granted_tags)),
                        _escape_cell(", ".join(form.blocked_tags)),
                        _escape_cell(form.gear_handling),
                        _escape_cell(form.default_duration_turns),
                    ]
                )
                + " |"
            )
        lines.append("")

    return "\n".join(lines)


def evaluate_tier_a_gold_corpus(ruleset_paths: Sequence[Path]) -> TierAEvalReport:
    """Run Track-1 deterministic evaluation across gold fixtures (JSON, MD tables & 14 probes)."""
    if not ruleset_paths:
        raise ValueError("ruleset_paths must not be empty.")

    scores: list[FixtureEvalScore] = []
    for path in ruleset_paths:
        errors: list[str] = []
        pkg_id = path.parent.name
        json_ok = False
        md_ok = False
        probe_absent_acc = 1.0
        invented: list[str] = []

        try:
            ruleset, _ = import_ruleset_file(path)
            pkg_id = ruleset.manifest.package_id
            json_ok = True

            # Verify Markdown table serializer -> parse_markdown -> import_structured_tables
            md_text = render_ruleset_as_markdown_tables(ruleset)
            md_doc = parse_markdown(md_text, source_name=f"{pkg_id}.md")
            md_ruleset, _ = import_structured_tables(
                md_doc,
                package_id=pkg_id,
                name=ruleset.manifest.name,
            )
            md_ok = (
                set(md_ruleset.properties) == set(ruleset.properties)
                and set(md_ruleset.resource_pools) == set(ruleset.resource_pools)
                and set(md_ruleset.resolutions) == set(ruleset.resolutions)
                and set(md_ruleset.conditions) == set(ruleset.conditions)
                and set(md_ruleset.actions) == set(ruleset.actions)
                and set(md_ruleset.forms) == set(ruleset.forms)
            )
            if not md_ok:
                errors.append("Markdown round-trip block sets differed from JSON source.")

            # Verify 14 lifecycle probes maintain strict Null/Absent guarantee
            probe_results = run_ruleset_schema_probes(ruleset)
            probe_map = {pr.domain_id: pr for pr in probe_results}
            raw_json = json.loads(path.read_text(encoding="utf-8"))
            _ = raw_json
            cap_probe = probe_map.get("capabilities_forms_covert")
            if (
                not ruleset.forms
                and cap_probe is not None
                and "forms" in cap_probe.extracted_primitives
            ):
                invented.append("forms")
            if ruleset.covert_ops is None:
                if "covert_stealth" in probe_map["capabilities_forms_covert"].extracted_primitives:
                    invented.append("covert_stealth")
                if "covert_theft" in probe_map["capabilities_forms_covert"].extracted_primitives:
                    invented.append("covert_theft")
                if "covert_disguise" in probe_map["social_morale_disguise"].extracted_primitives:
                    invented.append("covert_disguise")

            absent_checks = [
                pr
                for pr in probe_results
                if pr.domain_id
                in {
                    "world_cosmology",
                    "retinue_and_companions",
                    "vehicles_and_ontology",
                    "holdings_and_warfare",
                    "crafting_survival_economy",
                    "travel_dungeons_encounters",
                }
                and not (set(pr.extracted_primitives) & set(ruleset.declared_primitives))
            ]
            if absent_checks:
                ok_absent = sum(
                    1
                    for pr in absent_checks
                    if pr.status == "absent" and pr.declared_value == "none"
                )
                probe_absent_acc = round(ok_absent / len(absent_checks), 4)
                for pr in absent_checks:
                    if pr.status != "absent":
                        invented.append(pr.domain_id)

        except (OSError, ValueError, DocumentParseError, IngestionValidationError) as exc:
            errors.append(str(exc))

        scores.append(
            FixtureEvalScore(
                package_id=pkg_id,
                json_import_ok=json_ok,
                markdown_roundtrip_ok=md_ok,
                probe_absent_accuracy=probe_absent_acc,
                invented_domains=tuple(sorted(set(invented))),
                errors=tuple(errors),
            )
        )

    passed = sum(
        1
        for s in scores
        if s.json_import_ok
        and s.markdown_roundtrip_ok
        and s.probe_absent_accuracy == 1.0
        and not s.invented_domains
        and not s.errors
    )
    total = len(scores)
    return TierAEvalReport(
        total_fixtures=total,
        passed_fixtures=passed,
        pass_rate=round(passed / total, 4),
        fixture_scores=tuple(scores),
        all_passed=(passed == total),
    )


def evaluate_tier_b_extraction(
    doc: ParsedDocument,
    expectation: TierBGoldExpectation,
    *,
    micro_probe_fn: Callable[[TierBMicroProbeRequest], Mapping[str, object] | ProbeDomainResult],
    max_chunk_chars: int = 6000,
) -> TierBEvalReport:
    """Run Track-2 Tier-B evaluation verifying >=90% accuracy, 0 inventions & checkpoint parity."""
    max_tokens_seen = 0

    def _recording_probe(
        req: TierBMicroProbeRequest,
    ) -> Mapping[str, object] | ProbeDomainResult:
        nonlocal max_tokens_seen
        if req.estimated_tokens > max_tokens_seen:
            max_tokens_seen = req.estimated_tokens
        return micro_probe_fn(req)

    # Full run vs pause/resume split at 7 domains
    full_results, _ = run_tier_b_micro_probes(
        doc,
        micro_probe_fn=_recording_probe,
        max_chunk_chars=max_chunk_chars,
    )
    half_results, cp1 = run_tier_b_micro_probes(
        doc,
        micro_probe_fn=micro_probe_fn,
        max_chunk_chars=max_chunk_chars,
        max_domains_per_call=7,
    )
    _ = half_results
    resumed_results, _ = run_tier_b_micro_probes(
        doc,
        micro_probe_fn=micro_probe_fn,
        checkpoint=cp1,
        max_chunk_chars=max_chunk_chars,
    )
    checkpoint_identical = [r.model_dump(mode="json") for r in full_results] == [
        r.model_dump(mode="json") for r in resumed_results
    ]

    by_domain = {r.domain_id: r for r in full_results}
    total_checks = 0
    passed_checks = 0
    invented: list[str] = []

    for dom in expectation.expected_present_domains:
        total_checks += 1
        res = by_domain.get(dom)
        if res is not None and res.status in {"found", "partial"}:
            passed_checks += 1

    for dom in expectation.expected_absent_domains:
        total_checks += 1
        res = by_domain.get(dom)
        if res is not None and res.status == "absent" and res.declared_value == "none":
            passed_checks += 1
        elif res is not None:
            invented.append(dom)

    emitted_keys = {prop.block_key for res in full_results for prop in res.proposals} | {
        prim for res in full_results for prim in res.extracted_primitives
    }
    for key in expectation.expected_block_keys:
        total_checks += 1
        if key in emitted_keys:
            passed_checks += 1

    accuracy = round(passed_checks / total_checks, 4) if total_checks > 0 else 1.0
    passed = (
        accuracy >= 0.90 and len(invented) == 0 and max_tokens_seen <= 8192 and checkpoint_identical
    )
    return TierBEvalReport(
        doc_id=doc.doc_id,
        core_mechanics_accuracy=accuracy,
        false_positive_invented_domains=tuple(sorted(invented)),
        max_prompt_tokens_used=max_tokens_seen,
        checkpoint_resume_identical=checkpoint_identical,
        passed=passed,
    )
