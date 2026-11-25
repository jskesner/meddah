"""Deterministic on-demand JIT Compendium Block Compiler with content-hash caching."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from app.ingestion.models import CompendiumEntry, SourceCitation, slugify_anchor
from app.ruleset_vm import (
    ActionBlock,
    ConditionBlock,
    EntityState,
    FormBlock,
    RulesetSchema,
    ScalarValue,
)

CompiledBlockKind = Literal["action", "condition", "form", "entity"]

_KV_LINE_RE = re.compile(r"^([A-Za-z][A-Za-z0-9 _-]{0,32}):\s*(.+)$")

_ACTION_CATEGORY_MAP: dict[str, Literal["action", "power", "reaction", "stance"]] = {
    "action": "action",
    "power": "power",
    "spell": "power",
    "reaction": "reaction",
    "stance": "stance",
}
_FORM_MODE_MAP: dict[str, Literal["replace_all", "replace_subset", "delta_overlay"]] = {
    "replace_all": "replace_all",
    "replace_subset": "replace_subset",
    "delta_overlay": "delta_overlay",
}
_GEAR_MODE_MAP: dict[str, Literal["merge_into_form", "keep_worn", "drop_to_room"]] = {
    "merge_into_form": "merge_into_form",
    "keep_worn": "keep_worn",
    "drop_to_room": "drop_to_room",
}


class CompiledBlockResult(BaseModel):
    """Deterministically compiled Ruleset VM building block or entity template."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    entry_id: str = Field(min_length=1)
    content_hash: str = Field(min_length=1)
    block_kind: CompiledBlockKind
    compiled_payload: dict[str, object]
    from_cache: bool = False
    citation: SourceCitation


def _extract_fields(entry: CompendiumEntry) -> dict[str, str]:
    merged: dict[str, str] = {}
    for line in entry.body.splitlines():
        match = _KV_LINE_RE.match(line.strip())
        if match:
            key = match.group(1).strip().lower().replace(" ", "_").replace("-", "_")
            merged[key] = match.group(2).strip()
    for key, val in entry.structured_fields.items():
        merged[key.strip().lower().replace(" ", "_").replace("-", "_")] = val.strip()
    return merged


def _parse_scalar(raw: str) -> ScalarValue:
    stripped = raw.strip()
    if stripped.lower() in {"", "none", "null"}:
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


def _parse_kv(raw: str) -> dict[str, str]:
    stripped = raw.strip()
    if not stripped:
        return {}
    if stripped.startswith("{"):
        parsed: object = json.loads(stripped)
        if isinstance(parsed, dict):
            return {str(k): str(v) for k, v in cast(dict[object, object], parsed).items()}
    out: dict[str, str] = {}
    for chunk in re.split(r"[;,]", stripped):
        if "=" in chunk:
            k, v = chunk.split("=", 1)
            if k.strip():
                out[k.strip()] = v.strip()
    return out


def _parse_tuple(raw: str) -> tuple[str, ...]:
    if not raw.strip():
        return ()
    return tuple(tok.strip() for tok in re.split(r"[,;]", raw) if tok.strip())


class JitBlockCompiler:
    """Compiles indexed CompendiumEntry objects into validated VM blocks on demand."""

    def __init__(self) -> None:
        self._cache: dict[tuple[str, str], CompiledBlockResult] = {}

    def cache_size(self) -> int:
        """Return number of distinct cached compiled entries."""
        return len(self._cache)

    def clear_cache(self) -> None:
        """Clear compiled block cache."""
        self._cache.clear()

    def compile_entry(
        self,
        entry: CompendiumEntry,
        ruleset: RulesetSchema | None = None,
    ) -> CompiledBlockResult:
        """Deterministically compile a CompendiumEntry into a VM block or EntityState."""
        ruleset_key = ruleset.content_hash() if ruleset is not None else "no_ruleset"
        cache_key = (entry.entry_id, f"{entry.content_hash}:{ruleset_key}")
        if cache_key in self._cache:
            return self._cache[cache_key].model_copy(update={"from_cache": True})

        fields = _extract_fields(entry)
        base_id = (
            fields.get("id")
            or fields.get("action_id")
            or fields.get("condition_id")
            or fields.get("form_id")
            or fields.get("entity_id")
            or slugify_anchor(entry.title).replace("-", "_")
        )

        if entry.category == "condition":
            dur_raw = fields.get("default_duration_turns") or fields.get("duration") or ""
            dur = int(float(dur_raw)) if re.fullmatch(r"\d+", dur_raw) else None
            cond_block = ConditionBlock(
                condition_id=base_id,
                label=entry.title,
                description=entry.body[:400],
                property_modifiers=_parse_kv(fields.get("property_modifiers", "")),
                blocks_tags=_parse_tuple(fields.get("blocks_tags", "")),
                default_duration_turns=dur,
            )
            block_kind: CompiledBlockKind = "condition"
            payload = cond_block.model_dump(mode="json")

        elif entry.category == "form":
            prop_vals: dict[str, ScalarValue] = {
                k: _parse_scalar(v) for k, v in _parse_kv(fields.get("property_values", "")).items()
            }
            dur_raw = fields.get("default_duration_turns") or fields.get("duration") or ""
            dur = int(float(dur_raw)) if re.fullmatch(r"\d+", dur_raw) else None
            form_block = FormBlock(
                form_id=base_id,
                label=entry.title,
                description=entry.body[:400],
                property_mode=_FORM_MODE_MAP.get(
                    fields.get("property_mode", "replace_subset"), "replace_subset"
                ),
                property_values=prop_vals,
                property_deltas=_parse_kv(fields.get("property_deltas", "")),
                granted_tags=tuple(
                    sorted(set(_parse_tuple(fields.get("granted_tags", ""))) | set(entry.tags))
                ),
                blocked_tags=_parse_tuple(fields.get("blocked_tags", "")),
                gear_handling=_GEAR_MODE_MAP.get(
                    fields.get("gear_handling", "merge_into_form"), "merge_into_form"
                ),
                default_duration_turns=dur,
            )
            block_kind = "form"
            payload = form_block.model_dump(mode="json")

        elif entry.category == "creature":
            raw_props = _parse_kv(fields.get("properties", ""))
            base_props: dict[str, ScalarValue] = {k: _parse_scalar(v) for k, v in raw_props.items()}
            raw_pools = _parse_kv(fields.get("pools", ""))
            pools: dict[str, int] = {
                k: int(float(v))
                for k, v in raw_pools.items()
                if re.fullmatch(r"-?\d+(?:\.\d+)?", v)
            }
            if ruleset is not None:
                for pid, prop_def in ruleset.properties.items():
                    if pid in fields and pid not in base_props:
                        base_props[pid] = _parse_scalar(fields[pid])
                    elif pid not in base_props and prop_def.formula is None:
                        base_props[pid] = prop_def.default_value
                for pool_id in ruleset.resource_pools:
                    if pool_id in fields and re.fullmatch(r"-?\d+", fields[pool_id]):
                        pools[pool_id] = int(fields[pool_id])
            entity = EntityState(
                entity_id=base_id,
                name=entry.title,
                base_properties=base_props,
                pools=pools,
                tags=tuple(sorted(set(entry.tags) | set(_parse_tuple(fields.get("tags", ""))))),
                granted_actions=_parse_tuple(fields.get("granted_actions", "")),
            )
            block_kind = "entity"
            payload = entity.model_dump(mode="json")

        else:
            res_id = fields.get("resolution_id") or None
            if ruleset is not None and res_id is not None and res_id not in ruleset.resolutions:
                res_id = None
            raw_costs = _parse_kv(fields.get("pool_costs", ""))
            if ruleset is not None:
                raw_costs = {k: v for k, v in raw_costs.items() if k in ruleset.resource_pools}
            act_block = ActionBlock(
                action_id=base_id,
                label=entry.title,
                category=_ACTION_CATEGORY_MAP.get(fields.get("category", "action"), "action"),
                resolution_id=res_id,
                requires=fields.get("requires") or "true",
                pool_costs=raw_costs,
                requires_target=(fields.get("requires_target", "").lower() == "true"),
                tags=tuple(sorted(set(entry.tags) | set(_parse_tuple(fields.get("tags", ""))))),
            )
            block_kind = "action"
            payload = act_block.model_dump(mode="json")

        result = CompiledBlockResult(
            entry_id=entry.entry_id,
            content_hash=entry.content_hash,
            block_kind=block_kind,
            compiled_payload=payload,
            from_cache=False,
            citation=entry.citation,
        )
        self._cache[cache_key] = result
        return result

    def batch_compile(
        self,
        entries: Sequence[CompendiumEntry],
        ruleset: RulesetSchema | None = None,
    ) -> tuple[CompiledBlockResult, ...]:
        """Deterministically batch-compile sorted CompendiumEntry records."""
        return tuple(
            self.compile_entry(entry, ruleset=ruleset)
            for entry in sorted(entries, key=lambda item: item.entry_id)
        )
