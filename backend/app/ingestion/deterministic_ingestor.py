"""Deterministic Tier-A ruleset importer, safe archive extractor, and heuristic extractor."""

from __future__ import annotations

import json
import re
import stat
import zipfile
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Literal, cast

import yaml
from pydantic import BaseModel, ValidationError

from app.ingestion.document_parser import DocumentParseError, parse_document_file
from app.ingestion.models import (
    BlockCategory,
    DiffStatus,
    ExtractedTable,
    IngestionStagingJob,
    ParsedDocument,
    SourceCitation,
    SourceKind,
    StagingBlockProposal,
    canonical_sha256,
    slugify_anchor,
)
from app.ruleset_vm import (
    ActionBlock,
    ConditionBlock,
    FormBlock,
    FormPoolMode,
    FormPoolSpec,
    PackageManifest,
    PropertyBlock,
    RandomizerSpec,
    ResolutionMechanicBlock,
    ResourcePoolBlock,
    RulesetSchema,
    ScalarValue,
)

MAX_ARCHIVE_ENTRIES = 10_000
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 250 * 1024 * 1024
MAX_ARCHIVE_COMPRESSION_RATIO = 100.0

_DRIVE_PREFIX_RE = re.compile(r"^[A-Za-z]:")
_DICE_FORMULA_RE = re.compile(r"\b(\d+d\d+(?:k[hl]\d+|!)?(?:\s*[+-]\s*\d+)?)\b", re.IGNORECASE)
_COIN_FLIP_RE = re.compile(r"\b(coin\s+flip|flip\s+a?\s*coin|heads\s+or\s+tails)\b", re.IGNORECASE)
_CARD_DRAW_RE = re.compile(
    r"\b(draw\s+(?:\d+\s+)?card|deck\s+of\s+cards|52-card|joker)\b", re.IGNORECASE
)
_DICE_POOL_RE = re.compile(
    r"\b(dice\s+pool|count\s+(?:hits|successes)|pool\s+of\s+d\d+)\b", re.IGNORECASE
)
_SEGMENT_CLOCK_RE = re.compile(r"\b(\d+)-segment\s+(?:clock|track)\b", re.IGNORECASE)


class IngestionValidationError(Exception):
    """Raised when imported ruleset data fails schema or graph validation."""

    def __init__(self, errors: tuple[str, ...]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


def _check_archive_member_safety(info: zipfile.ZipInfo) -> None:
    name = info.filename
    if not name:
        raise DocumentParseError("RPG-E3003", "Archive contains an empty member filename.")
    if name.startswith("/") or name.startswith("\\") or _DRIVE_PREFIX_RE.match(name):
        raise DocumentParseError("RPG-E3003", f"Archive member uses absolute path: {name!r}")
    normalized = name.replace("\\", "/")
    posix = PurePosixPath(normalized)
    if posix.is_absolute() or ".." in posix.parts:
        raise DocumentParseError("RPG-E3003", f"Archive path traversal rejected: {name!r}")
    mode = (info.external_attr >> 16) & 0o170000
    if stat.S_ISLNK(mode):
        raise DocumentParseError("RPG-E3003", f"Archive symbolic link rejected: {name!r}")
    if info.file_size > 0:
        if info.compress_size <= 0:
            raise DocumentParseError(
                "RPG-E3002", f"Suspicious zero compressed size on archive entry {name!r}"
            )
        ratio = info.file_size / info.compress_size
        if ratio > MAX_ARCHIVE_COMPRESSION_RATIO:
            raise DocumentParseError(
                "RPG-E3002",
                (
                    f"Archive entry {name!r} exceeds compression ratio "
                    f"{MAX_ARCHIVE_COMPRESSION_RATIO}:1"
                ),
            )


def safe_extract_ruleset_archive(archive_path: Path) -> dict[str, object]:
    """Validate zip-slip/symlink/zip-bomb constraints and load ruleset.json/.yaml."""
    if not zipfile.is_zipfile(archive_path):
        raise DocumentParseError("RPG-E3003", f"Invalid .rpgrules archive: '{archive_path.name}'.")

    with zipfile.ZipFile(archive_path, "r") as zf:
        infos = zf.infolist()
        if len(infos) > MAX_ARCHIVE_ENTRIES:
            raise DocumentParseError(
                "RPG-E3002",
                f"Archive entry count {len(infos)} exceeds max {MAX_ARCHIVE_ENTRIES}.",
            )

        total_uncompressed = 0
        candidates: list[zipfile.ZipInfo] = []
        for info in infos:
            _check_archive_member_safety(info)
            total_uncompressed += info.file_size
            if total_uncompressed > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
                raise DocumentParseError(
                    "RPG-E3002",
                    f"Archive uncompressed size exceeds {MAX_ARCHIVE_UNCOMPRESSED_BYTES} bytes.",
                )
            posix = PurePosixPath(info.filename.replace("\\", "/"))
            if posix.name.lower() in {"ruleset.json", "ruleset.yaml", "ruleset.yml"}:
                candidates.append(info)

        if not candidates:
            raise IngestionValidationError(
                ("Archive does not contain ruleset.json or ruleset.yaml.",)
            )

        chosen = min(
            candidates, key=lambda item: (len(PurePosixPath(item.filename).parts), item.filename)
        )
        raw_bytes = zf.read(chosen.filename)
        if len(raw_bytes) > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
            raise DocumentParseError("RPG-E3002", "Extracted ruleset file exceeds max byte limit.")

    text = raw_bytes.decode("utf-8", errors="replace")
    try:
        loaded: object = (
            json.loads(text) if chosen.filename.lower().endswith(".json") else yaml.safe_load(text)
        )
    except (json.JSONDecodeError, yaml.YAMLError) as exc:
        raise DocumentParseError(
            "RPG-E3003", f"Malformed ruleset payload in archive '{archive_path.name}': {exc}"
        ) from exc

    if not isinstance(loaded, dict):
        raise IngestionValidationError(("Top-level ruleset payload must be an object/mapping.",))
    return cast(dict[str, object], loaded)


def _lookup_existing_payload(
    existing_ruleset: RulesetSchema | None,
    category: BlockCategory,
    block_key: str,
) -> dict[str, object] | None:
    if existing_ruleset is None:
        return None
    if category == "manifest":
        return existing_ruleset.manifest.model_dump(mode="json")
    if category == "flow_config":
        return existing_ruleset.flow_config.model_dump(mode="json")
    attr_map = {
        "property": existing_ruleset.properties,
        "resource_pool": existing_ruleset.resource_pools,
        "resolution": existing_ruleset.resolutions,
        "condition": existing_ruleset.conditions,
        "action": existing_ruleset.actions,
        "event_hook": existing_ruleset.event_hooks,
        "deck": existing_ruleset.decks,
        "form": existing_ruleset.forms,
    }
    collection = attr_map.get(category)
    if collection is None or block_key not in collection:
        return None
    return collection[block_key].model_dump(mode="json")


def _compute_diff_status(
    existing_ruleset: RulesetSchema | None,
    category: BlockCategory,
    block_key: str,
    proposed_payload: dict[str, object],
) -> tuple[DiffStatus, dict[str, object] | None]:
    existing_payload = _lookup_existing_payload(existing_ruleset, category, block_key)
    if existing_payload is None:
        return "NEW", None
    if existing_payload == proposed_payload:
        return "UNCHANGED", existing_payload
    return "MODIFIED", existing_payload


def _proposal_id(category: str, key: str, payload: dict[str, object]) -> str:
    digest = canonical_sha256({"cat": category, "key": key, "payload": payload})[:10]
    return f"prop_{category}_{slugify_anchor(key)}_{digest}"


def _build_ruleset_proposals(
    ruleset: RulesetSchema,
    *,
    citation: SourceCitation,
    confidence_score: float,
    existing_ruleset: RulesetSchema | None,
    notes: str = "",
) -> tuple[StagingBlockProposal, ...]:
    proposals: list[StagingBlockProposal] = []

    def _add(category: BlockCategory, key: str, payload: dict[str, object]) -> None:
        diff_status, existing = _compute_diff_status(existing_ruleset, category, key, payload)
        proposals.append(
            StagingBlockProposal(
                proposal_id=_proposal_id(category, key, payload),
                block_category=category,
                block_key=key,
                proposed_payload=payload,
                confidence_score=confidence_score,
                source_citation=citation,
                diff_status=diff_status,
                existing_payload=existing,
                notes=notes,
            )
        )

    _add("manifest", "manifest", ruleset.manifest.model_dump(mode="json"))
    _add("flow_config", "flow_config", ruleset.flow_config.model_dump(mode="json"))

    sections: tuple[tuple[BlockCategory, Mapping[str, BaseModel]], ...] = (
        ("property", ruleset.properties),
        ("resource_pool", ruleset.resource_pools),
        ("resolution", ruleset.resolutions),
        ("condition", ruleset.conditions),
        ("action", ruleset.actions),
        ("event_hook", ruleset.event_hooks),
        ("deck", ruleset.decks),
        ("form", ruleset.forms),
    )
    for category, mapping in sections:
        for key in sorted(mapping):
            model_obj = mapping[key]
            dumped = cast(dict[str, object], model_obj.model_dump(mode="json"))
            _add(category, key, dumped)
    return tuple(proposals)


def import_ruleset_data(
    data: Mapping[str, object],
    *,
    source_name: str,
    source_kind: SourceKind = "json",
    existing_ruleset: RulesetSchema | None = None,
) -> tuple[RulesetSchema, IngestionStagingJob]:
    """Validate structured ruleset JSON/YAML mapping into a RulesetSchema and StagingJob."""
    try:
        ruleset = RulesetSchema.model_validate(data)
    except ValidationError as exc:
        err_msgs = tuple(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors())
        raise IngestionValidationError(err_msgs) from exc

    graph_errors = ruleset.validate_graph()
    if graph_errors:
        raise IngestionValidationError(tuple(graph_errors))

    citation = SourceCitation(
        source_name=source_name,
        source_kind=source_kind,
        heading_path=(ruleset.manifest.name,),
        excerpt=f"Structured {source_kind.upper()} ruleset '{ruleset.manifest.package_id}'",
    )
    proposals = _build_ruleset_proposals(
        ruleset,
        citation=citation,
        confidence_score=1.0,
        existing_ruleset=existing_ruleset,
        notes="Imported deterministically from validated structured ruleset schema.",
    )
    job = IngestionStagingJob(
        job_id=f"job_{canonical_sha256((source_name, ruleset.content_hash()))[:12]}",
        source_name=source_name,
        source_kind=source_kind,
        status="ready_for_review",
        proposals=proposals,
    )
    return ruleset, job


def import_ruleset_file(
    path: Path,
    *,
    existing_ruleset: RulesetSchema | None = None,
) -> tuple[RulesetSchema, IngestionStagingJob]:
    """Deterministically import a .json, .yaml/.yml, or .rpgrules ruleset package."""
    suffix = path.suffix.lower()
    if suffix == ".rpgrules":
        raw_map = safe_extract_ruleset_archive(path)
        return import_ruleset_data(
            raw_map,
            source_name=path.name,
            source_kind="rpgrules",
            existing_ruleset=existing_ruleset,
        )

    if suffix in {".yaml", ".yml", ".json"}:
        kind: SourceKind = "json" if suffix == ".json" else "yaml"
        doc = parse_document_file(path, sandboxed=True)
        try:
            loaded: object = (
                json.loads(doc.raw_text) if kind == "json" else yaml.safe_load(doc.raw_text)
            )
        except (json.JSONDecodeError, yaml.YAMLError) as exc:
            raise IngestionValidationError((f"Failed to decode structured file: {exc}",)) from exc
        if not isinstance(loaded, dict):
            raise IngestionValidationError(("Ruleset root payload must be a JSON/YAML object.",))
        ruleset, job = import_ruleset_data(
            cast(dict[str, object], loaded),
            source_name=path.name,
            source_kind=kind,
            existing_ruleset=existing_ruleset,
        )
        return ruleset, job.model_copy(update={"documents": (doc,)})

    if suffix in {".md", ".markdown", ".csv"}:
        doc = parse_document_file(path, sandboxed=True)
        pkg_id = slugify_anchor(path.stem).replace("-", "_") or "imported_ruleset"
        ruleset, job = import_structured_tables(
            doc,
            package_id=pkg_id,
            name=doc.title or path.stem,
            existing_ruleset=existing_ruleset,
        )
        return ruleset, job.model_copy(update={"documents": (doc,)})

    raise DocumentParseError(
        "RPG-E3003", f"Unsupported ruleset file format '{path.suffix}' on '{path.name}'."
    )


def _table_row_to_map(table: ExtractedTable, row: tuple[str, ...]) -> dict[str, str]:
    out: dict[str, str] = {}
    for idx, hdr in enumerate(table.headers):
        key = hdr.strip().lower().replace(" ", "_")
        if not key:
            continue
        val = row[idx].strip() if idx < len(row) else ""
        out[key] = val
    return out


def _parse_scalar(raw: str) -> ScalarValue:
    stripped = raw.strip()
    if not stripped or stripped.lower() == "none" or stripped.lower() == "null":
        return None
    if stripped.lower() == "true":
        return True
    if stripped.lower() == "false":
        return False
    try:
        return int(stripped)
    except ValueError:
        pass
    try:
        return float(stripped)
    except ValueError:
        return stripped


def _parse_opt_int(raw: str) -> int | None:
    stripped = raw.strip()
    if not stripped or stripped.lower() in {"none", "null", "-"}:
        return None
    return int(float(stripped))


def _parse_str_tuple(raw: str) -> tuple[str, ...]:
    if not raw.strip():
        return ()
    return tuple(item.strip() for item in re.split(r"[,;]", raw) if item.strip())


def _parse_kv_map(raw: str) -> dict[str, str]:
    stripped = raw.strip()
    if not stripped:
        return {}
    if stripped.startswith("{"):
        parsed: object = json.loads(stripped)
        if isinstance(parsed, dict):
            return {str(k): str(v) for k, v in cast(dict[object, object], parsed).items()}
    pairs: dict[str, str] = {}
    for entry in re.split(r"[;,]", stripped):
        if "=" in entry:
            k, v = entry.split("=", 1)
            if k.strip():
                pairs[k.strip()] = v.strip()
        elif ":" in entry:
            k, v = entry.split(":", 1)
            if k.strip():
                pairs[k.strip()] = v.strip()
    return pairs


def _classify_table_domain(table: ExtractedTable) -> BlockCategory | None:
    cols = {hdr.strip().lower().replace(" ", "_") for hdr in table.headers}
    title_l = table.title.lower()
    if "prop_id" in cols or ("id" in cols and "propert" in title_l):
        return "property"
    if "pool_id" in cols or ("id" in cols and ("pool" in title_l or "resource" in title_l)):
        return "resource_pool"
    if "mech_id" in cols or ("id" in cols and "resolution" in title_l):
        return "resolution"
    if "condition_id" in cols or ("id" in cols and ("condition" in title_l or "status" in title_l)):
        return "condition"
    if "action_id" in cols or ("id" in cols and ("action" in title_l or "spell" in title_l)):
        return "action"
    if "form_id" in cols or ("id" in cols and ("form" in title_l or "transform" in title_l)):
        return "form"
    return None


_VALUE_KIND_MAP: dict[str, Literal["int", "float", "bool", "str", "step_die"]] = {
    "int": "int",
    "float": "float",
    "bool": "bool",
    "str": "str",
    "step_die": "step_die",
}
_RANDOMIZER_KIND_MAP: dict[
    str,
    Literal[
        "dice_formula",
        "dice_pool",
        "step_dice",
        "coin_flip",
        "card_deck",
        "resource_wager",
        "none",
    ],
] = {
    "dice_formula": "dice_formula",
    "dice_pool": "dice_pool",
    "step_dice": "step_dice",
    "coin_flip": "coin_flip",
    "card_deck": "card_deck",
    "resource_wager": "resource_wager",
    "none": "none",
}
_ACTION_CATEGORY_MAP: dict[str, Literal["action", "power", "reaction", "stance"]] = {
    "action": "action",
    "power": "power",
    "reaction": "reaction",
    "stance": "stance",
}
_FORM_PROPERTY_MODE_MAP: dict[str, Literal["replace_all", "replace_subset", "delta_overlay"]] = {
    "replace_all": "replace_all",
    "replace_subset": "replace_subset",
    "delta_overlay": "delta_overlay",
}
_GEAR_HANDLING_MAP: dict[str, Literal["merge_into_form", "keep_worn", "drop_to_room"]] = {
    "merge_into_form": "merge_into_form",
    "keep_worn": "keep_worn",
    "drop_to_room": "drop_to_room",
}


def import_structured_tables(
    doc: ParsedDocument,
    *,
    package_id: str,
    name: str,
    version: str = "0.1.0",
    existing_ruleset: RulesetSchema | None = None,
) -> tuple[RulesetSchema, IngestionStagingJob]:
    """Compile normalized Markdown/CSV/HTML primitive tables into a validated RulesetSchema."""
    props: dict[str, PropertyBlock] = {}
    pools: dict[str, ResourcePoolBlock] = {}
    resolutions: dict[str, ResolutionMechanicBlock] = {}
    conditions: dict[str, ConditionBlock] = {}
    actions: dict[str, ActionBlock] = {}
    forms: dict[str, FormBlock] = {}
    proposals: list[StagingBlockProposal] = []

    def _stage(cat: BlockCategory, key: str, model_obj: BaseModel, cit: SourceCitation) -> None:
        payload = cast(dict[str, object], model_obj.model_dump(mode="json"))
        diff_status, existing = _compute_diff_status(existing_ruleset, cat, key, payload)
        proposals.append(
            StagingBlockProposal(
                proposal_id=_proposal_id(cat, key, payload),
                block_category=cat,
                block_key=key,
                proposed_payload=payload,
                confidence_score=0.95,
                source_citation=cit,
                diff_status=diff_status,
                existing_payload=existing,
                notes="Compiled deterministically from structured table.",
            )
        )

    for tbl in doc.tables:
        domain = _classify_table_domain(tbl)
        if domain is None:
            continue
        for row in tbl.rows:
            rmap = _table_row_to_map(tbl, row)
            if domain == "property":
                pid = rmap.get("prop_id") or rmap.get("id") or ""
                if not pid:
                    continue
                default_val = _parse_scalar(rmap.get("default_value", "0"))
                raw_kind = rmap.get("value_kind") or (
                    "str"
                    if isinstance(default_val, str)
                    else ("bool" if isinstance(default_val, bool) else "int")
                )
                val_kind = _VALUE_KIND_MAP.get(raw_kind, "int")
                block = PropertyBlock(
                    prop_id=pid,
                    label=rmap.get("label") or pid.replace("_", " ").title(),
                    value_kind=val_kind,
                    default_value=default_val,
                    formula=rmap.get("formula") or None,
                    category=rmap.get("category") or "core",
                    tags=_parse_str_tuple(rmap.get("tags", "")),
                )
                props[pid] = block
                _stage("property", pid, block, tbl.citation)

            elif domain == "resource_pool":
                pool_id = rmap.get("pool_id") or rmap.get("id") or ""
                if not pool_id:
                    continue
                raw_def = rmap.get("default_current", "0")
                def_cur: int | str = (
                    int(float(raw_def))
                    if re.fullmatch(r"-?\d+(?:\.\d+)?", raw_def or "")
                    else (raw_def or "0")
                )
                pool_block = ResourcePoolBlock(
                    pool_id=pool_id,
                    label=rmap.get("label") or pool_id.replace("_", " ").title(),
                    default_current=def_cur,
                    max_formula=rmap.get("max_formula") or None,
                    min_value=_parse_opt_int(rmap.get("min_value", "0")) or 0,
                    reset_on=rmap.get("reset_on") or "manual",
                    track_segments=_parse_opt_int(rmap.get("track_segments", "")),
                )
                pools[pool_id] = pool_block
                _stage("resource_pool", pool_id, pool_block, tbl.citation)

            elif domain == "resolution":
                mech_id = rmap.get("mech_id") or rmap.get("id") or ""
                if not mech_id:
                    continue
                rand_kind = _RANDOMIZER_KIND_MAP.get(
                    rmap.get("randomizer_kind") or "dice_formula", "dice_formula"
                )
                rand_formula = rmap.get("formula") or rmap.get("dice_formula") or ""
                mech = ResolutionMechanicBlock(
                    mech_id=mech_id,
                    label=rmap.get("label") or mech_id.replace("_", " ").title(),
                    randomizer=RandomizerSpec(
                        kind=rand_kind,
                        formula=rand_formula,
                        coin_heads_label=rmap.get("coin_heads_label") or "heads",
                        coin_tails_label=rmap.get("coin_tails_label") or "tails",
                    ),
                    modifier_formula=rmap.get("modifier_formula") or "0",
                    target_formula=rmap.get("target_formula") or None,
                )
                resolutions[mech_id] = mech
                _stage("resolution", mech_id, mech, tbl.citation)

            elif domain == "condition":
                cid = rmap.get("condition_id") or rmap.get("id") or ""
                if not cid:
                    continue
                cond = ConditionBlock(
                    condition_id=cid,
                    label=rmap.get("label") or cid.replace("_", " ").title(),
                    description=rmap.get("description", ""),
                    property_modifiers=_parse_kv_map(rmap.get("property_modifiers", "")),
                    blocks_tags=_parse_str_tuple(rmap.get("blocks_tags", "")),
                    default_duration_turns=_parse_opt_int(rmap.get("default_duration_turns", "")),
                )
                conditions[cid] = cond
                _stage("condition", cid, cond, tbl.citation)

            elif domain == "action":
                aid = rmap.get("action_id") or rmap.get("id") or ""
                if not aid:
                    continue
                act = ActionBlock(
                    action_id=aid,
                    label=rmap.get("label") or aid.replace("_", " ").title(),
                    category=_ACTION_CATEGORY_MAP.get(rmap.get("category") or "action", "action"),
                    resolution_id=rmap.get("resolution_id") or None,
                    requires=rmap.get("requires") or "true",
                    pool_costs=_parse_kv_map(rmap.get("pool_costs", "")),
                    requires_target=(rmap.get("requires_target", "").lower() == "true"),
                    tags=_parse_str_tuple(rmap.get("tags", "")),
                )
                actions[aid] = act
                _stage("action", aid, act, tbl.citation)

            elif domain == "form":
                fid = rmap.get("form_id") or rmap.get("id") or ""
                if not fid:
                    continue
                prop_vals_raw = _parse_kv_map(rmap.get("property_values", ""))
                prop_vals: dict[str, ScalarValue] = {
                    k: _parse_scalar(v) for k, v in prop_vals_raw.items()
                }
                pool_policies: dict[str, FormPoolSpec] = {}
                pool_mode_raw = rmap.get("pool_mode", "")
                target_pool = rmap.get("target_pool", "vitality")
                if pool_mode_raw:
                    pool_policies[target_pool] = FormPoolSpec(
                        mode=cast(FormPoolMode, pool_mode_raw),
                        initial_formula=rmap.get("pool_initial_formula") or "0",
                        max_formula=rmap.get("pool_max_formula") or None,
                    )
                form = FormBlock(
                    form_id=fid,
                    label=rmap.get("label") or fid.replace("_", " ").title(),
                    description=rmap.get("description", ""),
                    property_mode=_FORM_PROPERTY_MODE_MAP.get(
                        rmap.get("property_mode") or "replace_subset", "replace_subset"
                    ),
                    property_values=prop_vals,
                    property_deltas=_parse_kv_map(rmap.get("property_deltas", "")),
                    pool_policies=pool_policies,
                    granted_tags=_parse_str_tuple(rmap.get("granted_tags", "")),
                    blocked_tags=_parse_str_tuple(rmap.get("blocked_tags", "")),
                    gear_handling=_GEAR_HANDLING_MAP.get(
                        rmap.get("gear_handling") or "merge_into_form", "merge_into_form"
                    ),
                    default_duration_turns=_parse_opt_int(rmap.get("default_duration_turns", "")),
                )
                forms[fid] = form
                _stage("form", fid, form, tbl.citation)

    if not any([props, pools, resolutions, conditions, actions, forms]):
        raise IngestionValidationError(
            (
                "No structured universal primitive tables "
                "(properties, pools, conditions, actions, forms) found.",
            )
        )

    ruleset = RulesetSchema(
        manifest=PackageManifest(
            package_type="ruleset",
            package_id=package_id,
            name=name,
            version=version,
        ),
        properties=props,
        resource_pools=pools,
        resolutions=resolutions,
        conditions=conditions,
        actions=actions,
        forms=forms,
    )
    graph_errors = ruleset.validate_graph()
    if graph_errors:
        raise IngestionValidationError(tuple(graph_errors))

    job = IngestionStagingJob(
        job_id=f"job_{canonical_sha256((doc.doc_id, ruleset.content_hash()))[:12]}",
        source_name=doc.source_name,
        source_kind=doc.source_kind,
        status="ready_for_review",
        documents=(doc,),
        proposals=tuple(proposals),
    )
    return ruleset, job


def extract_heuristic_proposals(
    doc: ParsedDocument,
    *,
    existing_ruleset: RulesetSchema | None = None,
) -> tuple[StagingBlockProposal, ...]:
    """Scan unstructured document text for dice/coin/card mechanics, forms, conditions & pools."""
    proposals: list[StagingBlockProposal] = []
    seen_keys: set[tuple[BlockCategory, str]] = set()

    def _emit(
        category: BlockCategory,
        key: str,
        payload: dict[str, object],
        confidence: float,
        citation: SourceCitation,
        notes: str,
    ) -> None:
        if (category, key) in seen_keys:
            return
        seen_keys.add((category, key))
        diff_status, existing = _compute_diff_status(existing_ruleset, category, key, payload)
        proposals.append(
            StagingBlockProposal(
                proposal_id=_proposal_id(category, key, payload),
                block_category=category,
                block_key=key,
                proposed_payload=payload,
                confidence_score=confidence,
                source_citation=citation,
                diff_status=diff_status,
                existing_payload=existing,
                notes=notes,
            )
        )

    for sec in doc.sections:
        combined = f"{sec.heading}\n{sec.body}".strip()
        heading_l = sec.heading.lower()
        body_l = sec.body.lower()
        citation = SourceCitation(
            source_name=doc.source_name,
            source_kind=doc.source_kind,
            page_number=sec.page_number,
            url=sec.url,
            anchor=sec.anchor,
            heading_path=sec.heading_path,
            excerpt=" ".join(combined.split())[:240],
        )

        # Heuristic randomizer/resolution detection
        if _COIN_FLIP_RE.search(combined):
            key = f"{slugify_anchor(sec.heading).replace('-', '_')}_coin_flip"
            mech = ResolutionMechanicBlock(
                mech_id=key,
                label=f"{sec.heading} Coin Flip",
                randomizer=RandomizerSpec(kind="coin_flip", pool_size_formula="1"),
            )
            _emit(
                "resolution",
                key,
                mech.model_dump(mode="json"),
                0.75,
                citation,
                "Detected coin flip resolution heuristic.",
            )
        elif _CARD_DRAW_RE.search(combined):
            key = f"{slugify_anchor(sec.heading).replace('-', '_')}_card_draw"
            mech = ResolutionMechanicBlock(
                mech_id=key,
                label=f"{sec.heading} Card Draw",
                randomizer=RandomizerSpec(kind="card_deck", deck_id="main_deck"),
            )
            _emit(
                "resolution",
                key,
                mech.model_dump(mode="json"),
                0.70,
                citation,
                "Detected card deck resolution heuristic.",
            )
        elif _DICE_POOL_RE.search(combined):
            key = f"{slugify_anchor(sec.heading).replace('-', '_')}_dice_pool"
            mech = ResolutionMechanicBlock(
                mech_id=key,
                label=f"{sec.heading} Dice Pool",
                randomizer=RandomizerSpec(kind="dice_pool", pool_size_formula="3", die_sides=6),
            )
            _emit(
                "resolution",
                key,
                mech.model_dump(mode="json"),
                0.75,
                citation,
                "Detected dice pool resolution heuristic.",
            )
        else:
            dice_match = _DICE_FORMULA_RE.search(combined)
            if dice_match:
                formula = re.sub(r"\s+", "", dice_match.group(1)).lower()
                key = f"{slugify_anchor(sec.heading).replace('-', '_')}_check"
                mech = ResolutionMechanicBlock(
                    mech_id=key,
                    label=f"{sec.heading} Check",
                    randomizer=RandomizerSpec(kind="dice_formula", formula=formula),
                )
                _emit(
                    "resolution",
                    key,
                    mech.model_dump(mode="json"),
                    0.80,
                    citation,
                    f"Detected dice notation '{formula}'.",
                )

        # Alternate form / transformation block heuristic
        if any(kw in heading_l for kw in ("form", "shapeshift", "transform", "chassis", "morph")):
            fid = slugify_anchor(sec.heading).replace("-", "_")
            form = FormBlock(
                form_id=fid,
                label=sec.heading,
                description=sec.body[:240],
                property_mode="replace_subset",
            )
            _emit(
                "form",
                fid,
                form.model_dump(mode="json"),
                0.70,
                citation,
                "Detected alternate form / transformation heading.",
            )

        # Condition / ailment heuristic
        if any(kw in heading_l for kw in ("condition", "status", "ailment", "affliction")):
            cid = slugify_anchor(sec.heading).replace("-", "_")
            cond = ConditionBlock(
                condition_id=cid,
                label=sec.heading,
                description=sec.body[:240],
            )
            _emit(
                "condition",
                cid,
                cond.model_dump(mode="json"),
                0.70,
                citation,
                "Detected status condition heading.",
            )

        # Resource pool / progress clock heuristic
        seg_match = _SEGMENT_CLOCK_RE.search(combined)
        if seg_match or any(
            kw in heading_l for kw in ("pool", "track", "vitality", "sanity", "stamina")
        ):
            pid = slugify_anchor(sec.heading).replace("-", "_")
            segments = int(seg_match.group(1)) if seg_match else None
            pool = ResourcePoolBlock(
                pool_id=pid,
                label=sec.heading,
                track_segments=segments,
            )
            _emit(
                "resource_pool",
                pid,
                pool.model_dump(mode="json"),
                0.65,
                citation,
                "Detected resource pool or segmented progress clock.",
            )

        # Action / capability heuristic
        if any(
            kw in heading_l or f"{kw}:" in body_l
            for kw in ("action", "power", "spell", "maneuver", "attack", "reaction", "stance")
        ):
            aid = slugify_anchor(sec.heading).replace("-", "_")
            act_cat: Literal["action", "power", "reaction", "stance"] = (
                "reaction"
                if "reaction" in heading_l
                else (
                    "stance"
                    if "stance" in heading_l
                    else ("power" if any(k in heading_l for k in ("power", "spell")) else "action")
                )
            )
            act = ActionBlock(
                action_id=aid,
                label=sec.heading,
                category=act_cat,
            )
            _emit(
                "action",
                aid,
                act.model_dump(mode="json"),
                0.65,
                citation,
                "Detected capability/action rule heuristic.",
            )

    return tuple(proposals)


def ingest_document_deterministically(
    doc: ParsedDocument,
    *,
    existing_ruleset: RulesetSchema | None = None,
    package_id: str = "draft_ruleset",
    name: str | None = None,
) -> IngestionStagingJob:
    """Run deterministic table import and heuristic extraction into a staging job."""
    warnings: list[str] = list(doc.warnings)
    table_proposals: tuple[StagingBlockProposal, ...] = ()
    if doc.tables:
        try:
            _, table_job = import_structured_tables(
                doc,
                package_id=package_id,
                name=name or doc.title or doc.source_name,
                existing_ruleset=existing_ruleset,
            )
            table_proposals = table_job.proposals
        except IngestionValidationError as exc:
            warnings.extend(exc.errors)

    heuristic_proposals = extract_heuristic_proposals(doc, existing_ruleset=existing_ruleset)
    combined_by_key: dict[tuple[BlockCategory, str], StagingBlockProposal] = {}
    final_proposals: list[StagingBlockProposal] = []

    for prop in (*table_proposals, *heuristic_proposals):
        ident = (prop.block_category, prop.block_key)
        if ident in combined_by_key:
            prior = combined_by_key[ident]
            if prior.proposed_payload != prop.proposed_payload:
                final_proposals.append(
                    prop.model_copy(
                        update={
                            "diff_status": "CONFLICT",
                            "notes": f"Conflicts with earlier extracted '{prop.block_key}'.",
                        }
                    )
                )
            continue
        combined_by_key[ident] = prop
        final_proposals.append(prop)

    return IngestionStagingJob(
        job_id=f"job_{canonical_sha256((doc.doc_id, len(final_proposals)))[:12]}",
        source_name=doc.source_name,
        source_kind=doc.source_kind,
        status="ready_for_review",
        documents=(doc,),
        proposals=tuple(final_proposals),
        warnings=tuple(warnings),
    )
