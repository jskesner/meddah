"""Shared Pydantic schemas & ModuleRegistry manifest for Phase 2 Ingestion (§1.2)."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.ruleset_vm.module_registry import MeddahModuleManifest, ModuleProvides

MODULE_MANIFEST = MeddahModuleManifest(
    module_id="ingestion_studio",
    spec_section="1.2",
    label="Ruleset Ingestion Pipeline & Compendium Studio",
    requires_primitives=(),
    provides=ModuleProvides(
        commands=("ingest", "index", "compile_entry", "probe", "simulate", "workbench"),
        ui_panels=("ingestion_workbench", "compendium_studio"),
        schema_blocks=(
            "IngestionStagingJob",
            "CompendiumEntry",
            "ProbeDomainResult",
            "RulesetPatchSpec",
            "BalanceSimulationReport",
        ),
        studio_editors=("ruleset_studio", "diff_workbench"),
    ),
    scope="campaign",
    ai_dependency="none",
)

SourceKind = Literal[
    "markdown",
    "txt",
    "html",
    "json",
    "yaml",
    "csv",
    "pdf",
    "rpgrules",
    "url",
]
DiffStatus = Literal["NEW", "MODIFIED", "CONFLICT", "UNCHANGED", "NOT_FOUND_IN_SOURCE"]
ProposalDecision = Literal["pending", "accepted", "merged", "edited", "skipped"]
BlockCategory = Literal[
    "manifest",
    "property",
    "resource_pool",
    "resolution",
    "condition",
    "action",
    "event_hook",
    "deck",
    "form",
    "covert_ops",
    "flow_config",
    "compendium",
    "rule_note",
]
CompendiumCategory = Literal[
    "action",
    "condition",
    "form",
    "creature",
    "item",
    "table",
    "rule_note",
]
SubpageStatus = Literal[
    "pending",
    "fetched",
    "not_modified",
    "paused_captcha",
    "manual_submitted",
    "skipped",
    "blocked_robots",
    "failed",
]
StagingJobStatus = Literal[
    "staging",
    "ready_for_review",
    "paused_captcha",
    "committed",
    "failed",
]
ProbeStatus = Literal["found", "partial", "absent"]

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def canonical_sha256(value: object) -> str:
    """Compute canonical deterministic SHA-256 hex digest for text, bytes, or mappings."""
    if isinstance(value, bytes):
        raw = value
    elif isinstance(value, str):
        raw = value.encode("utf-8")
    else:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def slugify_anchor(text: str) -> str:
    """Convert heading text into a clean lowercase anchor slug."""
    slug = _SLUG_RE.sub("-", text.lower()).strip("-")
    return slug or "section"


class SourceCitation(BaseModel):
    """Exact source provenance attached to every extracted section, table, or proposal."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_name: str = Field(min_length=1)
    source_kind: SourceKind
    page_number: int | None = Field(default=None, ge=1)
    url: str | None = None
    anchor: str | None = None
    heading_path: tuple[str, ...] = ()
    excerpt: str = ""


class ExtractedTable(BaseModel):
    """Normalized structural table extracted from Markdown, CSV, HTML, or PDF sources."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    table_id: str = Field(min_length=1)
    title: str = ""
    headers: tuple[str, ...] = ()
    rows: tuple[tuple[str, ...], ...] = ()
    citation: SourceCitation


class DocumentSection(BaseModel):
    """Normalized hierarchical section extracted from an ingested rulebook document."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    section_id: str = Field(min_length=1)
    heading: str = ""
    level: int = Field(default=1, ge=1, le=6)
    anchor: str = Field(default="section", min_length=1)
    heading_path: tuple[str, ...] = ()
    body: str = ""
    page_number: int | None = Field(default=None, ge=1)
    url: str | None = None
    tables: tuple[ExtractedTable, ...] = ()
    content_hash: str = Field(min_length=1)


class ParsedDocument(BaseModel):
    """Normalized multi-format Structural Document AST produced by document_parser."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    doc_id: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    source_kind: SourceKind
    title: str = ""
    raw_text: str = ""
    sections: tuple[DocumentSection, ...] = ()
    tables: tuple[ExtractedTable, ...] = ()
    content_hash: str = Field(min_length=1)
    warnings: tuple[str, ...] = ()


class CompendiumEntry(BaseModel):
    """Indexed reference rule/creature/item/ability record stored in SQLite FTS5."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    entry_id: str = Field(min_length=1)
    category: CompendiumCategory = "rule_note"
    title: str = Field(min_length=1)
    body: str = ""
    tags: tuple[str, ...] = ()
    structured_fields: dict[str, str] = Field(default_factory=dict)
    citation: SourceCitation
    content_hash: str = Field(min_length=1)


class CompendiumSearchHit(BaseModel):
    """Ranked BM25 match returned by CompendiumIndex."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    entry: CompendiumEntry
    bm25_score: float
    snippet: str = ""


class StagingBlockProposal(BaseModel):
    """Proposed VM building block staged for review in the Diff Workbench."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    proposal_id: str = Field(min_length=1)
    block_category: BlockCategory
    block_key: str = Field(min_length=1)
    proposed_payload: dict[str, object] = Field(default_factory=dict)
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)
    source_citation: SourceCitation
    diff_status: DiffStatus = "NEW"
    decision: ProposalDecision = "pending"
    existing_payload: dict[str, object] | None = None
    notes: str = ""


class ProbeDomainResult(BaseModel):
    """Result record for one of the 14 semantic & lifecycle discovery probes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    probe_number: int = Field(ge=1, le=14)
    domain_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    status: ProbeStatus
    declared_value: str = "none"
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    extracted_primitives: tuple[str, ...] = ()
    proposals: tuple[StagingBlockProposal, ...] = ()
    citations: tuple[SourceCitation, ...] = ()
    summary: str = ""


class SubpageDiscoveryCandidate(BaseModel):
    """Same-origin sub-page link presented in the interactive checklist before fetching."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    url: str = Field(min_length=1)
    title: str = ""
    chapter_group: str = "root"
    depth: int = Field(default=1, ge=1, le=2)
    selected: bool = True


class SubpageFetchRecord(BaseModel):
    """Per-URL fetch state and conditional cache metadata in an IngestionStagingJob."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    url: str = Field(min_length=1)
    title: str = ""
    chapter_group: str = "root"
    status: SubpageStatus = "pending"
    etag: str | None = None
    last_modified: str | None = None
    content_hash: str | None = None
    raw_content: str = ""
    content_kind: Literal["html", "markdown", "txt", "pdf"] = "html"
    challenge_vendor: str | None = None
    error_message: str | None = None


class CaptchaPauseReport(BaseModel):
    """Structured pause-in-place state when an anti-bot or CAPTCHA gate is detected."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    paused_url: str = Field(min_length=1)
    challenge_vendor: str = Field(min_length=1)
    http_status: int | None = None
    reason: str = Field(min_length=1)
    recovery_options: tuple[str, ...] = (
        "browser_verification_window",
        "manual_paste_or_file_drop",
        "skip_page",
    )


class PoliteFetchPolicy(BaseModel):
    """Polite single-concurrency anti-DDoS and SSRF fetch configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_concurrent_requests: Literal[1] = 1
    min_delay_seconds: float = Field(default=1.5, ge=0.0)
    max_delay_seconds: float = Field(default=3.0, ge=0.0)
    jitter_seconds: float = Field(default=0.5, ge=0.0)
    request_timeout_seconds: float = Field(default=15.0, gt=0.0)
    max_response_bytes: int = Field(default=10 * 1024 * 1024, gt=0)
    max_redirects: int = Field(default=3, ge=0, le=10)
    max_pages_per_job: int = Field(default=25, ge=1, le=500)
    max_discovery_depth: int = Field(default=1, ge=1, le=2)
    max_rate_limit_retries: int = Field(default=2, ge=0, le=10)
    user_agent: str = "MeddahRulesetIngestor/0.2 (+https://meddah.local)"
    rng_seed: str = "meddah-polite-fetch"


class IngestionStagingJob(BaseModel):
    """Persistent staging bundle reviewed in the Diff Workbench prior to ruleset commit."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    job_id: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    source_kind: SourceKind
    status: StagingJobStatus = "staging"
    documents: tuple[ParsedDocument, ...] = ()
    proposals: tuple[StagingBlockProposal, ...] = ()
    probe_results: tuple[ProbeDomainResult, ...] = ()
    subpages: tuple[SubpageFetchRecord, ...] = ()
    captcha_pause: CaptchaPauseReport | None = None
    warnings: tuple[str, ...] = ()
