"""14-Domain Semantic & Lifecycle Discovery Probes with strict Null/Absent guarantee (§1.2)."""

from __future__ import annotations

import json
import urllib.request
from collections.abc import Callable, Mapping
from typing import cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.ingestion.compendium_index import CompendiumIndex
from app.ingestion.models import (
    BlockCategory,
    DiffStatus,
    ParsedDocument,
    ProbeDomainResult,
    ProbeStatus,
    SourceCitation,
    StagingBlockProposal,
    canonical_sha256,
    slugify_anchor,
)
from app.ruleset_vm import (
    ConditionBlock,
    CovertOpsConfigBlock,
    DisguisePillarConfig,
    FormBlock,
    RulesetSchema,
    StealthPillarConfig,
    TheftPillarConfig,
)


class ProbeDomainSpec(BaseModel):
    """Definition of one universal RPG domain searched during ingestion probes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    probe_number: int = Field(ge=1, le=14)
    domain_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    keywords: tuple[str, ...] = Field(min_length=1)
    heading_hints: tuple[str, ...] = ()
    schema_primitives: tuple[str, ...] = ()


FOURTEEN_PROBE_DOMAINS: tuple[ProbeDomainSpec, ...] = (
    ProbeDomainSpec(
        probe_number=1,
        domain_id="vitality_and_death",
        label="Vitality, Incapacitation & Death Mechanics",
        keywords=(
            "vitality",
            "wound",
            "harm",
            "injury",
            "unconscious",
            "dying",
            "bleeding",
            "incapacitated",
            "death",
            "hit location",
            "amputation",
            "critical injury",
            "mortality",
        ),
        heading_hints=("vitality", "harm", "wound", "injury", "dying", "death", "hit location"),
        schema_primitives=("vitality_topology", "hit_locations"),
    ),
    ProbeDomainSpec(
        probe_number=2,
        domain_id="stabilization_and_medical",
        label="Stabilization, Medical, Surgery & Restoration",
        keywords=(
            "first aid",
            "triage",
            "stabilize",
            "stabilization",
            "surgery",
            "surgical",
            "recuperation",
            "prosthetic",
            "cybernetic",
            "healing",
            "medicine",
            "resurrection",
            "revive",
            "restoration",
        ),
        heading_hints=("healing", "medical", "surgery", "stabilize", "resurrection"),
        schema_primitives=("medical_pipeline",),
    ),
    ProbeDomainSpec(
        probe_number=3,
        domain_id="rest_and_downtime",
        label="Rest, Downtime & Resource Recovery",
        keywords=(
            "short rest",
            "long rest",
            "breather",
            "campfire",
            "make camp",
            "watch shift",
            "watch rotation",
            "downtime",
            "indulge",
            "vice",
            "resting",
        ),
        heading_hints=("rest", "camp", "downtime", "recovery"),
        schema_primitives=("rest_and_downtime",),
    ),
    ProbeDomainSpec(
        probe_number=4,
        domain_id="creation_and_advancement",
        label="Character Creation & Advancement Rules",
        keywords=(
            "point buy",
            "standard array",
            "random roll",
            "lifepath",
            "character creation",
            "advancement",
            "milestone",
            "xp",
            "karma",
            "skill tick",
            "playbook",
            "tier up",
        ),
        heading_hints=("creation", "advancement", "progression", "experience", "lifepath"),
        schema_primitives=("creation_graph", "advancement_graph"),
    ),
    ProbeDomainSpec(
        probe_number=5,
        domain_id="tactical_spatial",
        label="Tactical Spatial, Movement, Cover & Elevation",
        keywords=(
            "square grid",
            "hex grid",
            "gridless",
            "abstract zone",
            "theater of the mind",
            "elevation",
            "flight",
            "falling",
            "cover",
            "flanking",
            "line of sight",
            "spatial grid",
        ),
        heading_hints=("tactical", "movement", "grid", "zones", "cover", "elevation"),
        schema_primitives=("spatial_grid",),
    ),
    ProbeDomainSpec(
        probe_number=6,
        domain_id="world_cosmology",
        label="World Cosmology, Macro Scales, Z-Strata & Planes",
        keywords=(
            "cosmology",
            "z-stratum",
            "underdark",
            "subterranean",
            "planar",
            "mirror realm",
            "hyperspace",
            "warp",
            "megacity",
            "vacuum",
            "star sector",
            "astral",
        ),
        heading_hints=("cosmology", "planes", "strata", "sectors", "world"),
        schema_primitives=("world_cosmology",),
    ),
    ProbeDomainSpec(
        probe_number=7,
        domain_id="social_morale_disguise",
        label="Social Contests, Morale, Disguises, Sanity & Reputation",
        keywords=(
            "persuasion",
            "intimidation",
            "deception",
            "social contest",
            "disguise",
            "alias",
            "impersonate",
            "sanity",
            "corruption",
            "morale",
            "rout",
            "reputation",
            "humanity",
        ),
        heading_hints=("social", "disguise", "sanity", "morale", "reputation", "corruption"),
        schema_primitives=("covert_disguise", "social_contests"),
    ),
    ProbeDomainSpec(
        probe_number=8,
        domain_id="capabilities_forms_covert",
        label="Capabilities, Spells, Stances, Reactions, Alternate Forms & Stealth/Theft",
        keywords=(
            "action",
            "spell",
            "reaction",
            "stance",
            "cooldown",
            "ritual",
            "concentration",
            "resource pool",
            "alternate form",
            "shapeshift",
            "polymorph",
            "lycanthrop",
            "chassis",
            "stealth",
            "hidden",
            "pickpocket",
            "sleight of hand",
            "theft",
        ),
        heading_hints=(
            "action",
            "spell",
            "power",
            "reaction",
            "stance",
            "form",
            "shapeshift",
            "stealth",
            "theft",
        ),
        schema_primitives=("resolution_mechanic", "forms", "covert_stealth", "covert_theft"),
    ),
    ProbeDomainSpec(
        probe_number=9,
        domain_id="retinue_and_companions",
        label="Retinue, Pets, Familiars, Mounts, Drones & Summons",
        keywords=(
            "companion",
            "retinue",
            "familiar",
            "mount",
            "drone",
            "minion",
            "summon",
            "hireling",
            "loyalty",
        ),
        heading_hints=("companion", "retinue", "familiar", "mount", "summon"),
        schema_primitives=("retinue_engine",),
    ),
    ProbeDomainSpec(
        probe_number=10,
        domain_id="vehicles_and_ontology",
        label="Pilotable Vehicles, Vessels & Setting Tech Ontology",
        keywords=(
            "vehicle",
            "starship",
            "naval ship",
            "airship",
            "mech",
            "caravan",
            "crew station",
            "hull",
            "cargo",
            "fuel",
            "tech tier",
            "currency",
            "coinage",
        ),
        heading_hints=("vehicle", "starship", "ship", "mech", "currency", "tech"),
        schema_primitives=("vehicles",),
    ),
    ProbeDomainSpec(
        probe_number=11,
        domain_id="holdings_and_warfare",
        label="Holdings, Strongholds, Bastions & Mass Warfare",
        keywords=(
            "stronghold",
            "bastion",
            "headquarters",
            "holding",
            "lair",
            "facility upkeep",
            "domain",
            "siege",
            "mass warfare",
            "army",
            "regiment",
        ),
        heading_hints=("stronghold", "bastion", "holding", "warfare", "siege"),
        schema_primitives=("holdings", "mass_units"),
    ),
    ProbeDomainSpec(
        probe_number=12,
        domain_id="crafting_survival_economy",
        label="Crafting, Alchemy, Traps, Survival, Encumbrance & Loot",
        keywords=(
            "crafting",
            "smithing",
            "alchemy",
            "enchanting",
            "trap",
            "disarm",
            "foraging",
            "ration",
            "exhaustion",
            "encumbrance",
            "loot table",
            "barter",
            "merchant",
        ),
        heading_hints=("craft", "alchemy", "trap", "survival", "encumbrance", "loot", "economy"),
        schema_primitives=("crafting", "survival_mode"),
    ),
    ProbeDomainSpec(
        probe_number=13,
        domain_id="travel_dungeons_encounters",
        label="Overworld Travel, Multi-Floor Dungeons & Random Encounters",
        keywords=(
            "overworld",
            "hex crawl",
            "forced march",
            "navigation",
            "dungeon turn",
            "torch",
            "random encounter",
            "wandering monster",
            "weather hazard",
            "travel pace",
        ),
        heading_hints=("travel", "overworld", "dungeon", "encounter", "exploration"),
        schema_primitives=("overworld_travel",),
    ),
    ProbeDomainSpec(
        probe_number=14,
        domain_id="piety_dreams_and_law",
        label="Deities, Piety, Patrons, Dreams & Law/Crime/Covert Enforcement",
        keywords=(
            "deity",
            "piety",
            "devotion",
            "oath",
            "anathema",
            "patron",
            "pact",
            "dream",
            "omen",
            "bounty",
            "wanted level",
            "witness",
            "arrest",
            "prison",
            "contraband",
            "stolen",
        ),
        heading_hints=("piety", "deity", "patron", "dream", "law", "crime", "bounty"),
        schema_primitives=("piety_patrons", "law_witnesses"),
    ),
)

DOMAIN_BY_ID: dict[str, ProbeDomainSpec] = {spec.domain_id: spec for spec in FOURTEEN_PROBE_DOMAINS}


class TierBMicroProbeRequest(BaseModel):
    """Token-bounded micro-probe request passed cleanly to Tier-B local LLM or adapter."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    probe_number: int = Field(ge=1, le=14)
    domain_id: str
    label: str
    prompt_text: str
    estimated_tokens: int = Field(ge=1)
    chunk_citations: tuple[SourceCitation, ...] = ()
    response_json_schema: dict[str, object] = Field(default_factory=dict)


class ProbeCheckpointState(BaseModel):
    """Per-probe checkpoint state allowing long Tier-B ingestion runs to pause & resume."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    doc_id: str = Field(min_length=1)
    completed_domains: dict[str, ProbeDomainResult] = Field(default_factory=dict)
    pending_domain_ids: tuple[str, ...] = ()


class OllamaMicroProbeClient:
    """Zero-dependency HTTP JSON-schema client calling a local Ollama endpoint (Tier B)."""

    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:11434",
        model: str = "qwen2.5:7b-instruct",
        timeout_seconds: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    def __call__(self, request: TierBMicroProbeRequest) -> dict[str, object]:
        """Execute a grammar-constrained JSON-schema micro-probe against local Ollama."""
        body = json.dumps(
            {
                "model": self.model,
                "prompt": request.prompt_text,
                "stream": False,
                "format": request.response_json_schema,
                "options": {"temperature": 0},
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
        response_text = str(raw.get("response", "{}"))
        parsed = json.loads(response_text)
        if not isinstance(parsed, dict):
            raise ValueError("Ollama micro-probe response must be a JSON object.")
        return cast(dict[str, object], parsed)


def _proposal_diff_status(
    existing_ruleset: RulesetSchema | None,
    category: BlockCategory,
    key: str,
    payload: dict[str, object],
) -> tuple[DiffStatus, dict[str, object] | None]:
    if existing_ruleset is None:
        return "NEW", None
    existing_map: dict[str, BaseModel] = {}
    if category == "form":
        existing_map = cast(dict[str, BaseModel], dict(existing_ruleset.forms))
    elif category == "condition":
        existing_map = cast(dict[str, BaseModel], dict(existing_ruleset.conditions))
    elif category == "action":
        existing_map = cast(dict[str, BaseModel], dict(existing_ruleset.actions))
    elif category == "covert_ops" and existing_ruleset.covert_ops is not None:
        existing_payload = cast(
            dict[str, object], existing_ruleset.covert_ops.model_dump(mode="json")
        )
        if existing_payload == payload:
            return "UNCHANGED", existing_payload
        return "MODIFIED", existing_payload
    if key not in existing_map:
        return "NEW", None
    existing_payload = cast(dict[str, object], existing_map[key].model_dump(mode="json"))
    if existing_payload == payload:
        return "UNCHANGED", existing_payload
    return "MODIFIED", existing_payload


def _make_probe_proposal(
    *,
    category: BlockCategory,
    key: str,
    payload: dict[str, object],
    confidence: float,
    citation: SourceCitation,
    existing_ruleset: RulesetSchema | None,
    notes: str,
) -> StagingBlockProposal:
    diff_status, existing = _proposal_diff_status(existing_ruleset, category, key, payload)
    digest = canonical_sha256({"cat": category, "key": key, "payload": payload})[:12]
    return StagingBlockProposal(
        proposal_id=f"probe_{category}_{key}_{digest}",
        block_category=category,
        block_key=key,
        proposed_payload=payload,
        confidence_score=confidence,
        source_citation=citation,
        diff_status=diff_status,
        existing_payload=existing,
        notes=notes,
    )


def _detect_covert_evidence(text: str) -> tuple[bool, bool, bool]:
    lower = text.lower()
    has_stealth = any(
        kw in lower for kw in ("stealth", "hidden", "sneak", "undetected", "camouflage")
    )
    has_theft = any(
        kw in lower
        for kw in ("pickpocket", "sleight of hand", "theft", "steal", "contraband", "stolen")
    )
    has_disguise = any(
        kw in lower for kw in ("disguise", "impersonate", "alias", "forged identity", "mask")
    )
    return has_stealth, has_theft, has_disguise


def _detect_vitality_mode(text: str) -> str:
    lower = text.lower()
    if "composite_dual" in lower or ("hit location" in lower and "total vitality" in lower):
        return "composite_dual"
    if "independent_locations" in lower or "hit location" in lower or "limb" in lower:
        return "independent_locations"
    return "monolithic"


def _detect_spatial_mode(text: str) -> str:
    lower = text.lower()
    if "hex grid" in lower or "hex" in lower:
        return "hex_grid"
    if "square grid" in lower or "spatial grid" in lower:
        return "square_grid"
    if "abstract zone" in lower or "zone" in lower:
        return "abstract_zones"
    if "theater of the mind" in lower:
        return "theater_of_mind"
    return "declared"


def _build_domain_proposals(
    spec: ProbeDomainSpec,
    matched_sections_text: list[tuple[str, str, SourceCitation]],
    doc: ParsedDocument,
    existing_ruleset: RulesetSchema | None,
) -> tuple[StagingBlockProposal, ...]:
    if not matched_sections_text:
        return ()
    proposals: list[StagingBlockProposal] = []
    primary_citation = matched_sections_text[0][2]
    combined = "\n".join(f"{h}\n{b}" for h, b, _ in matched_sections_text)

    if spec.domain_id == "vitality_and_death":
        for heading, body, cit in matched_sections_text:
            h_low = heading.lower()
            if any(term in h_low for term in ("dying", "unconscious", "bleeding", "incapacitated")):
                cid = slugify_anchor(heading).replace("-", "_")
                cond = ConditionBlock(
                    condition_id=cid,
                    label=heading or cid.replace("_", " ").title(),
                    description=body[:240]
                    or f"Lifecycle condition '{heading}' from {doc.source_name}.",
                    persistent_flag="dying" in h_low or "incapacitated" in h_low,
                )
                proposals.append(
                    _make_probe_proposal(
                        category="condition",
                        key=cid,
                        payload=cast(dict[str, object], cond.model_dump(mode="json")),
                        confidence=0.75,
                        citation=cit,
                        existing_ruleset=existing_ruleset,
                        notes=f"Probe #1 extracted lifecycle condition '{cid}'.",
                    )
                )

    if spec.domain_id == "capabilities_forms_covert":
        for heading, body, cit in matched_sections_text:
            h_low = heading.lower()
            if any(
                term in h_low for term in ("form", "shapeshift", "polymorph", "chassis", "morph")
            ):
                fid = slugify_anchor(heading).replace("-", "_")
                form = FormBlock(
                    form_id=fid,
                    label=heading or fid.replace("_", " ").title(),
                    description=body[:200],
                    property_mode="replace_subset",
                    granted_tags=(fid,),
                )
                proposals.append(
                    _make_probe_proposal(
                        category="form",
                        key=fid,
                        payload=cast(dict[str, object], form.model_dump(mode="json")),
                        confidence=0.72,
                        citation=cit,
                        existing_ruleset=existing_ruleset,
                        notes=f"Probe #8 extracted alternate FormBlock '{fid}'.",
                    )
                )
        has_stealth, has_theft, _ = _detect_covert_evidence(combined)
        _, _, has_disguise = _detect_covert_evidence(doc.raw_text)
        if has_stealth or has_theft or has_disguise:
            cfg = CovertOpsConfigBlock(
                stealth=StealthPillarConfig() if has_stealth else None,
                theft=TheftPillarConfig() if has_theft else None,
                disguise=DisguisePillarConfig() if has_disguise else None,
            )
            proposals.append(
                _make_probe_proposal(
                    category="covert_ops",
                    key="covert_ops",
                    payload=cast(dict[str, object], cfg.model_dump(mode="json")),
                    confidence=0.80,
                    citation=primary_citation,
                    existing_ruleset=existing_ruleset,
                    notes="Probes #7/#8/#14 extracted evidenced CovertOpsConfigBlock pillars.",
                )
            )

    elif spec.domain_id == "social_morale_disguise":
        _, _, has_disguise = _detect_covert_evidence(combined)
        full_stealth, full_theft, _ = _detect_covert_evidence(doc.raw_text)
        if has_disguise and not (full_stealth or full_theft):
            cfg = CovertOpsConfigBlock(disguise=DisguisePillarConfig())
            proposals.append(
                _make_probe_proposal(
                    category="covert_ops",
                    key="covert_ops",
                    payload=cast(dict[str, object], cfg.model_dump(mode="json")),
                    confidence=0.78,
                    citation=primary_citation,
                    existing_ruleset=existing_ruleset,
                    notes="Probe #7 extracted disguise-only CovertOpsConfigBlock.",
                )
            )

    return tuple(proposals)


def run_deterministic_probes(
    doc: ParsedDocument,
    *,
    compendium_index: CompendiumIndex | None = None,
    existing_ruleset: RulesetSchema | None = None,
) -> tuple[ProbeDomainResult, ...]:
    """Run all 14 Tier-A semantic & lifecycle probes with strict Null/Absent guarantee."""
    owns_index = compendium_index is None
    idx = compendium_index if compendium_index is not None else CompendiumIndex(":memory:")
    try:
        if owns_index and idx.count() == 0:
            idx.index_parsed_document(doc)

        results: list[ProbeDomainResult] = []
        for spec in FOURTEEN_PROBE_DOMAINS:
            matched_keywords: list[str] = []
            citations_by_anchor: dict[str, SourceCitation] = {}
            matched_sections: list[tuple[str, str, SourceCitation]] = []
            heading_hits = 0

            for sec in doc.sections:
                sec_lower = f"{sec.heading}\n{sec.body}".lower()
                heading_l = sec.heading.lower()
                sec_matches = [kw for kw in spec.keywords if kw in sec_lower]
                if sec_matches:
                    for kw in sec_matches:
                        if kw not in matched_keywords:
                            matched_keywords.append(kw)
                    if any(hint in heading_l for hint in spec.heading_hints):
                        heading_hits += 1
                    cit = SourceCitation(
                        source_name=doc.source_name,
                        source_kind=doc.source_kind,
                        page_number=sec.page_number,
                        url=sec.url,
                        anchor=sec.anchor,
                        heading_path=sec.heading_path,
                        excerpt=(sec.body or sec.heading)[:220],
                    )
                    cit_key = f"{sec.section_id}:{sec.anchor}"
                    if cit_key not in citations_by_anchor:
                        citations_by_anchor[cit_key] = cit
                        matched_sections.append((sec.heading, sec.body, cit))

            for tbl in doc.tables:
                tbl_text = " ".join(
                    [tbl.title, *tbl.headers, *(cell for row in tbl.rows for cell in row)]
                ).lower()
                tbl_matches = [kw for kw in spec.keywords if kw in tbl_text]
                if tbl_matches:
                    for kw in tbl_matches:
                        if kw not in matched_keywords:
                            matched_keywords.append(kw)
                    cit_key = f"tbl:{tbl.table_id}"
                    if cit_key not in citations_by_anchor:
                        citations_by_anchor[cit_key] = tbl.citation

            fts_hits = 0
            for kw in spec.keywords[:6]:
                if " " in kw:
                    continue
                for hit in idx.search(kw, limit=2):
                    fts_hits += 1
                    if kw not in matched_keywords:
                        matched_keywords.append(kw)
                    cit_key = f"fts:{hit.entry.entry_id}"
                    if cit_key not in citations_by_anchor:
                        citations_by_anchor[cit_key] = hit.entry.citation

            if not matched_keywords:
                results.append(
                    ProbeDomainResult(
                        probe_number=spec.probe_number,
                        domain_id=spec.domain_id,
                        label=spec.label,
                        status="absent",
                        declared_value="none",
                        confidence_score=0.0,
                        extracted_primitives=(),
                        proposals=(),
                        citations=(),
                        summary=f"No ruleset mechanics detected for '{spec.label}'; left dormant.",
                    )
                )
                continue

            status: ProbeStatus = (
                "found"
                if (len(matched_keywords) >= 2 or heading_hits >= 1 or fts_hits >= 2)
                else "partial"
            )
            confidence = min(
                0.98,
                round(0.45 + 0.12 * len(matched_keywords) + 0.15 * min(heading_hits, 2), 3),
            )
            combined_text = "\n".join(f"{h}\n{b}" for h, b, _ in matched_sections)
            declared_value = ", ".join(matched_keywords[:4])
            prims = list(spec.schema_primitives)
            if spec.domain_id == "vitality_and_death":
                declared_value = _detect_vitality_mode(combined_text or doc.raw_text)
            elif spec.domain_id == "tactical_spatial":
                declared_value = _detect_spatial_mode(combined_text or doc.raw_text)
            elif spec.domain_id == "capabilities_forms_covert":
                s_on, t_on, _ = _detect_covert_evidence(combined_text or doc.raw_text)
                prims = ["resolution_mechanic"]
                if any(
                    k in (combined_text or doc.raw_text).lower()
                    for k in ("form", "shapeshift", "polymorph", "chassis")
                ):
                    prims.append("forms")
                if s_on:
                    prims.append("covert_stealth")
                if t_on:
                    prims.append("covert_theft")
            elif spec.domain_id == "social_morale_disguise":
                _, _, d_on = _detect_covert_evidence(combined_text or doc.raw_text)
                prims = ["covert_disguise"] if d_on else ["social_contests"]

            proposals = _build_domain_proposals(spec, matched_sections, doc, existing_ruleset)
            results.append(
                ProbeDomainResult(
                    probe_number=spec.probe_number,
                    domain_id=spec.domain_id,
                    label=spec.label,
                    status=status,
                    declared_value=declared_value,
                    confidence_score=confidence,
                    extracted_primitives=tuple(dict.fromkeys(prims)),
                    proposals=proposals,
                    citations=tuple(citations_by_anchor.values())[:5],
                    summary=(
                        f"Detected {status} evidence ({declared_value}) across "
                        f"{len(citations_by_anchor)} citation(s)."
                    ),
                )
            )
        return tuple(results)
    finally:
        if owns_index:
            idx.close()


def run_ruleset_schema_probes(ruleset: RulesetSchema) -> tuple[ProbeDomainResult, ...]:
    """Deterministically inspect a compiled RulesetSchema across all 14 domains (0 inventions)."""
    declared_set = set(ruleset.declared_primitives)
    text_blob = " ".join(
        [
            *ruleset.properties.keys(),
            *(p.label for p in ruleset.properties.values()),
            *ruleset.resource_pools.keys(),
            *(p.label for p in ruleset.resource_pools.values()),
            *ruleset.conditions.keys(),
            *(f"{c.label} {c.description}" for c in ruleset.conditions.values()),
            *ruleset.actions.keys(),
            *(f"{a.label} {' '.join(a.tags)}" for a in ruleset.actions.values()),
            *ruleset.resolutions.keys(),
            *(r.label for r in ruleset.resolutions.values()),
        ]
    ).lower()

    results: list[ProbeDomainResult] = []
    for spec in FOURTEEN_PROBE_DOMAINS:
        found_prims: list[str] = [p for p in spec.schema_primitives if p in declared_set]
        declared_value = "none"
        status: ProbeStatus = "absent"

        if spec.domain_id == "vitality_and_death":
            if (
                ruleset.resource_pools
                or "hit_locations" in declared_set
                or any(k in text_blob for k in ("dying", "wound", "vitality", "harm", "bleed"))
            ):
                status = "found"
                declared_value = (
                    "independent_locations" if "hit_locations" in declared_set else "monolithic"
                )
        elif spec.domain_id == "stabilization_and_medical":
            if any(
                k in text_blob for k in ("stabilize", "first_aid", "heal", "medicine", "triage")
            ):
                status = "found"
                declared_value = "ruleset_medical_actions"
        elif spec.domain_id == "rest_and_downtime":
            if any(p.reset_on != "manual" for p in ruleset.resource_pools.values()) or any(
                k in text_blob for k in ("rest", "downtime", "camp")
            ):
                status = "found"
                declared_value = "pool_reset_or_rest_rules"
        elif spec.domain_id == "creation_and_advancement":
            if (
                ruleset.properties
                or "creation_graph" in declared_set
                or "advancement_graph" in declared_set
            ):
                status = "found" if ruleset.properties else "partial"
                declared_value = f"{len(ruleset.properties)} properties"
        elif spec.domain_id == "tactical_spatial":
            if (
                "spatial_grid" in declared_set
                or ruleset.flow_config.default_mode == "round_initiative"
            ):
                status = "found" if "spatial_grid" in declared_set else "partial"
                declared_value = (
                    "spatial_grid"
                    if "spatial_grid" in declared_set
                    else ruleset.flow_config.default_mode
                )
        elif spec.domain_id == "world_cosmology":
            if "world_cosmology" in declared_set:
                status = "found"
                declared_value = "declared"
        elif spec.domain_id == "social_morale_disguise":
            has_disguise = (
                ruleset.covert_ops is not None and ruleset.covert_ops.disguise is not None
            )
            if has_disguise or any(
                k in text_blob for k in ("sanity", "morale", "persuade", "intimidation", "disguise")
            ):
                status = "found"
                declared_value = "disguise_pillar" if has_disguise else "social_mechanics"
                if has_disguise and "covert_disguise" not in found_prims:
                    found_prims.append("covert_disguise")
        elif spec.domain_id == "capabilities_forms_covert":
            has_forms = bool(ruleset.forms)
            has_stealth = ruleset.covert_ops is not None and ruleset.covert_ops.stealth is not None
            has_theft = ruleset.covert_ops is not None and ruleset.covert_ops.theft is not None
            if ruleset.actions or ruleset.resolutions or has_forms or has_stealth or has_theft:
                status = "found"
                declared_value = (
                    f"{len(ruleset.actions)} actions, {len(ruleset.resolutions)} resolutions, "
                    f"{len(ruleset.forms)} forms"
                )
                if has_forms and "forms" not in found_prims:
                    found_prims.append("forms")
                if has_stealth and "covert_stealth" not in found_prims:
                    found_prims.append("covert_stealth")
                if has_theft and "covert_theft" not in found_prims:
                    found_prims.append("covert_theft")
        elif spec.domain_id == "piety_dreams_and_law":
            if any(p in declared_set for p in ("piety_patrons", "law_witnesses")) or any(
                k in text_blob for k in ("bounty", "contraband", "piety", "oath", "patron")
            ):
                status = "found"
                declared_value = "declared"
        elif found_prims:
            status = "found"
            declared_value = ", ".join(found_prims)

        results.append(
            ProbeDomainResult(
                probe_number=spec.probe_number,
                domain_id=spec.domain_id,
                label=spec.label,
                status=status,
                declared_value=declared_value,
                confidence_score=1.0
                if status == "found"
                else (0.5 if status == "partial" else 0.0),
                extracted_primitives=tuple(dict.fromkeys(found_prims)),
                summary=f"Schema audit: {status} ({declared_value}).",
            )
        )
    return tuple(results)


def run_tier_b_micro_probes(
    doc: ParsedDocument,
    *,
    micro_probe_fn: Callable[[TierBMicroProbeRequest], Mapping[str, object] | ProbeDomainResult],
    checkpoint: ProbeCheckpointState | None = None,
    max_chunk_chars: int = 6000,
    max_domains_per_call: int | None = None,
) -> tuple[tuple[ProbeDomainResult, ...], ProbeCheckpointState]:
    """Run token-bounded Tier-B micro-probes with per-probe checkpointing & Tier-A fallback."""
    if max_chunk_chars < 500:
        raise ValueError("max_chunk_chars must be >= 500.")

    completed: dict[str, ProbeDomainResult] = (
        dict(checkpoint.completed_domains)
        if checkpoint is not None and checkpoint.doc_id == doc.doc_id
        else {}
    )
    fallback_results = {r.domain_id: r for r in run_deterministic_probes(doc)}

    idx = CompendiumIndex(":memory:")
    try:
        idx.index_parsed_document(doc)
        schema_dict = cast(dict[str, object], ProbeDomainResult.model_json_schema())
        processed_this_call = 0

        for spec in FOURTEEN_PROBE_DOMAINS:
            if spec.domain_id in completed:
                continue
            if max_domains_per_call is not None and processed_this_call >= max_domains_per_call:
                break

            snippets: list[str] = []
            cits: list[SourceCitation] = []
            seen_entries: set[str] = set()
            for kw in spec.keywords:
                if " " in kw:
                    continue
                for hit in idx.search(kw, limit=2):
                    if hit.entry.entry_id in seen_entries:
                        continue
                    seen_entries.add(hit.entry.entry_id)
                    snippets.append(f"[{hit.entry.title}] {hit.entry.body[:600]}")
                    cits.append(hit.entry.citation)

            if not snippets:
                for sec in doc.sections[:4]:
                    if any(k in f"{sec.heading} {sec.body}".lower() for k in spec.keywords):
                        snippets.append(f"[{sec.heading}] {sec.body[:600]}")
                        cits.append(
                            SourceCitation(
                                source_name=doc.source_name,
                                source_kind=doc.source_kind,
                                page_number=sec.page_number,
                                url=sec.url,
                                anchor=sec.anchor,
                                heading_path=sec.heading_path,
                                excerpt=sec.body[:200],
                            )
                        )

            chunk_body = "\n".join(snippets)[:max_chunk_chars] or "NO_EVIDENCE_FOUND"
            prompt_text = (
                f"Probe #{spec.probe_number} ({spec.domain_id}): {spec.label}\n"
                "Extract ONLY explicitly declared mechanics; return status='absent' and "
                "declared_value='none' if absent.\n"
                f"Source excerpts:\n{chunk_body}"
            )[: max_chunk_chars + 400]
            est_tokens = max(1, (len(prompt_text) + 3) // 4)

            req = TierBMicroProbeRequest(
                probe_number=spec.probe_number,
                domain_id=spec.domain_id,
                label=spec.label,
                prompt_text=prompt_text,
                estimated_tokens=est_tokens,
                chunk_citations=tuple(cits[:5]),
                response_json_schema=schema_dict,
            )

            try:
                raw_out = micro_probe_fn(req)
                if isinstance(raw_out, ProbeDomainResult):
                    parsed = raw_out
                else:
                    merged = dict(raw_out)
                    merged.setdefault("probe_number", spec.probe_number)
                    merged.setdefault("domain_id", spec.domain_id)
                    merged.setdefault("label", spec.label)
                    parsed = ProbeDomainResult.model_validate(merged)
            except (ValidationError, ValueError, TypeError, KeyError):
                parsed = fallback_results[spec.domain_id]

            completed[spec.domain_id] = parsed
            processed_this_call += 1
    finally:
        idx.close()

    pending = tuple(
        spec.domain_id for spec in FOURTEEN_PROBE_DOMAINS if spec.domain_id not in completed
    )
    next_checkpoint = ProbeCheckpointState(
        doc_id=doc.doc_id,
        completed_domains=completed,
        pending_domain_ids=pending,
    )
    ordered = tuple(
        completed[spec.domain_id] for spec in FOURTEEN_PROBE_DOMAINS if spec.domain_id in completed
    )
    return ordered, next_checkpoint
