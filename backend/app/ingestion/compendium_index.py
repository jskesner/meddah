"""Deterministic SQLite FTS5 BM25 compendium indexer (Zero-VRAM Tier A & Tier B default)."""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Sequence
from pathlib import Path
from types import TracebackType
from typing import cast

from app.ingestion.models import (
    CompendiumCategory,
    CompendiumEntry,
    CompendiumSearchHit,
    ParsedDocument,
    SourceCitation,
    canonical_sha256,
    slugify_anchor,
)

_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")

_CATEGORY_KEYWORDS: tuple[tuple[CompendiumCategory, tuple[str, ...]], ...] = (
    ("form", ("form", "shape", "transform", "chassis", "morph", "alter_ego")),
    ("condition", ("condition", "status", "ailment", "affliction", "injur")),
    ("creature", ("creature", "bestiary", "monster", "adversary", "beast", "npc", "foe")),
    ("action", ("action", "power", "spell", "ritual", "maneuver", "ability", "reaction", "stance")),
    ("item", ("item", "equipment", "gear", "weapon", "armor", "apparel", "artifact", "consumable")),
    ("table", ("table", "oracle", "loot", "encounter", "random")),
)


def _infer_entry_category(title: str, body: str) -> CompendiumCategory:
    haystack = f"{title} {body[:200]}".lower()
    for category, keywords in _CATEGORY_KEYWORDS:
        if any(kw in haystack for kw in keywords):
            return category
    return "rule_note"


_FTS_OPERATOR_WORDS: frozenset[str] = frozenset({"AND", "OR", "NOT", "NEAR"})


def _build_fts_match_query(query: str) -> str | None:
    raw_tokens = _TOKEN_RE.findall(query)
    if not raw_tokens:
        return None
    tokens = [tok for tok in raw_tokens if tok not in _FTS_OPERATOR_WORDS] or raw_tokens
    return " ".join(f'"{tok}"' for tok in tokens)


def _collapse_snippet(text: str, limit: int = 180) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 3] + "..."


class CompendiumIndex:
    """Zero-AI SQLite FTS5 BM25 index storing normalized CompendiumEntry records."""

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self._db_path = str(db_path)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    def _init_schema(self) -> None:
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS compendium_entries (
                    entry_id TEXT PRIMARY KEY,
                    category TEXT NOT NULL,
                    title TEXT NOT NULL,
                    body TEXT NOT NULL,
                    tags_json TEXT NOT NULL,
                    structured_fields_json TEXT NOT NULL,
                    citation_json TEXT NOT NULL,
                    content_hash TEXT NOT NULL
                )
                """
            )
            self._conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS compendium_entries_fts USING fts5(
                    entry_id UNINDEXED,
                    category,
                    title,
                    body,
                    tags_text,
                    tokenize='porter unicode61'
                )
                """
            )

    def __enter__(self) -> CompendiumIndex:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        """Close the underlying SQLite connection cleanly."""
        self._conn.close()

    def _row_to_entry(self, row: sqlite3.Row) -> CompendiumEntry:
        tags_raw = json.loads(str(row["tags_json"]))
        fields_raw = json.loads(str(row["structured_fields_json"]))
        citation = SourceCitation.model_validate_json(str(row["citation_json"]))
        return CompendiumEntry(
            entry_id=str(row["entry_id"]),
            category=cast(CompendiumCategory, str(row["category"])),
            title=str(row["title"]),
            body=str(row["body"]),
            tags=tuple(str(item) for item in tags_raw),
            structured_fields={str(k): str(v) for k, v in fields_raw.items()},
            citation=citation,
            content_hash=str(row["content_hash"]),
        )

    def upsert_entry(self, entry: CompendiumEntry) -> None:
        """Insert or update a single CompendiumEntry in metadata and FTS5 tables."""
        self.upsert_entries((entry,))

    def upsert_entries(self, entries: Sequence[CompendiumEntry]) -> None:
        """Insert or update multiple CompendiumEntry rows atomically."""
        if not entries:
            return
        with self._conn:
            for entry in entries:
                tags_json = json.dumps(list(entry.tags))
                fields_json = json.dumps(entry.structured_fields, sort_keys=True)
                citation_json = entry.citation.model_dump_json()
                tags_text = " ".join(entry.tags)
                fields_text = " ".join(
                    f"{k} {v}" for k, v in sorted(entry.structured_fields.items())
                )
                searchable_body = f"{entry.body}\n{fields_text}".strip()

                self._conn.execute(
                    "DELETE FROM compendium_entries_fts WHERE entry_id = ?",
                    (entry.entry_id,),
                )
                self._conn.execute(
                    """
                    INSERT OR REPLACE INTO compendium_entries (
                        entry_id, category, title, body, tags_json,
                        structured_fields_json, citation_json, content_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        entry.entry_id,
                        entry.category,
                        entry.title,
                        entry.body,
                        tags_json,
                        fields_json,
                        citation_json,
                        entry.content_hash,
                    ),
                )
                self._conn.execute(
                    """
                    INSERT INTO compendium_entries_fts (
                        entry_id, category, title, body, tags_text
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        entry.entry_id,
                        entry.category,
                        entry.title,
                        searchable_body,
                        tags_text,
                    ),
                )

    def delete_entry(self, entry_id: str) -> bool:
        """Remove an entry by ID, returning True if a record was deleted."""
        with self._conn:
            self._conn.execute(
                "DELETE FROM compendium_entries_fts WHERE entry_id = ?",
                (entry_id,),
            )
            cur = self._conn.execute(
                "DELETE FROM compendium_entries WHERE entry_id = ?",
                (entry_id,),
            )
        return cur.rowcount > 0

    def get_entry(self, entry_id: str) -> CompendiumEntry | None:
        """Fetch an entry by ID, or return None if absent."""
        row = self._conn.execute(
            "SELECT * FROM compendium_entries WHERE entry_id = ?",
            (entry_id,),
        ).fetchone()
        return self._row_to_entry(row) if row is not None else None

    def list_entries(
        self,
        *,
        category: CompendiumCategory | None = None,
        tag: str | None = None,
    ) -> tuple[CompendiumEntry, ...]:
        """Return deterministically sorted entries optionally filtered by category and tag."""
        sql = "SELECT * FROM compendium_entries"
        params: list[object] = []
        if category is not None:
            sql += " WHERE category = ?"
            params.append(category)
        sql += " ORDER BY entry_id ASC"
        rows = self._conn.execute(sql, tuple(params)).fetchall()
        results: list[CompendiumEntry] = []
        for row in rows:
            entry = self._row_to_entry(row)
            if tag is not None and tag not in entry.tags:
                continue
            results.append(entry)
        return tuple(results)

    def count(self) -> int:
        """Return total number of indexed CompendiumEntry records."""
        row = self._conn.execute("SELECT COUNT(*) AS total FROM compendium_entries").fetchone()
        return int(row["total"]) if row is not None else 0

    def search(
        self,
        query: str,
        *,
        category: CompendiumCategory | None = None,
        tag: str | None = None,
        limit: int = 10,
    ) -> tuple[CompendiumSearchHit, ...]:
        """Run BM25 lexical search over indexed entries, safely sanitizing arbitrary queries."""
        if limit < 1:
            return ()
        match_expr = _build_fts_match_query(query)
        if match_expr is None:
            return ()

        sql = """
            SELECT
                meta.*,
                bm25(compendium_entries_fts) AS bm25_rank,
                snippet(compendium_entries_fts, 3, '[', ']', '...', 24) AS snip
            FROM compendium_entries_fts AS fts
            JOIN compendium_entries AS meta ON meta.entry_id = fts.entry_id
            WHERE compendium_entries_fts MATCH ?
        """
        params: list[object] = [match_expr]
        if category is not None:
            sql += " AND meta.category = ?"
            params.append(category)
        sql += " ORDER BY bm25_rank ASC, meta.entry_id ASC"
        if tag is None:
            sql += " LIMIT ?"
            params.append(limit)

        rows = self._conn.execute(sql, tuple(params)).fetchall()
        hits: list[CompendiumSearchHit] = []
        for row in rows:
            entry = self._row_to_entry(row)
            if tag is not None and tag not in entry.tags:
                continue
            snip_raw = str(row["snip"] or "").strip() or _collapse_snippet(
                entry.body or entry.title
            )
            hits.append(
                CompendiumSearchHit(
                    entry=entry,
                    bm25_score=float(row["bm25_rank"]),
                    snippet=snip_raw,
                )
            )
            if len(hits) >= limit:
                break
        return tuple(hits)

    def index_parsed_document(self, doc: ParsedDocument) -> int:
        """Convert ParsedDocument sections and table rows into deterministic FTS5 entries."""
        entries: list[CompendiumEntry] = []

        for sec in doc.sections:
            if not sec.heading and not sec.body:
                continue
            title = sec.heading or doc.title or doc.source_name
            category = _infer_entry_category(title, sec.body)
            tags = tuple(dict.fromkeys([category, slugify_anchor(title)]))
            entry_id = f"{doc.doc_id}_{sec.section_id}"
            citation = SourceCitation(
                source_name=doc.source_name,
                source_kind=doc.source_kind,
                page_number=sec.page_number,
                url=sec.url,
                anchor=sec.anchor,
                heading_path=sec.heading_path,
                excerpt=_collapse_snippet(sec.body or title, limit=240),
            )
            entries.append(
                CompendiumEntry(
                    entry_id=entry_id,
                    category=category,
                    title=title,
                    body=sec.body,
                    tags=tags,
                    structured_fields={},
                    citation=citation,
                    content_hash=canonical_sha256(
                        {"id": entry_id, "title": title, "body": sec.body}
                    ),
                )
            )

        for tbl in doc.tables:
            if not tbl.headers or not tbl.rows:
                continue
            for row_idx, row_vals in enumerate(tbl.rows, start=1):
                field_map = {
                    hdr: row_vals[idx] if idx < len(row_vals) else ""
                    for idx, hdr in enumerate(tbl.headers)
                    if hdr
                }
                field_lower = {k.lower(): v for k, v in field_map.items()}
                row_title = (
                    field_lower.get("label")
                    or field_lower.get("title")
                    or field_lower.get("name")
                    or (row_vals[0] if row_vals and row_vals[0] else f"{tbl.title} #{row_idx}")
                )
                row_body = "; ".join(f"{k}: {v}" for k, v in field_map.items() if v)
                category = _infer_entry_category(tbl.title, row_body)
                entry_id = f"{doc.doc_id}_{tbl.table_id}_row_{row_idx:04d}"
                citation = SourceCitation(
                    source_name=tbl.citation.source_name,
                    source_kind=tbl.citation.source_kind,
                    page_number=tbl.citation.page_number,
                    url=tbl.citation.url,
                    anchor=tbl.citation.anchor,
                    heading_path=tbl.citation.heading_path,
                    excerpt=_collapse_snippet(row_body or row_title, limit=240),
                )
                entries.append(
                    CompendiumEntry(
                        entry_id=entry_id,
                        category=category,
                        title=row_title,
                        body=row_body,
                        tags=tuple(dict.fromkeys([category, slugify_anchor(tbl.title or "table")])),
                        structured_fields=field_map,
                        citation=citation,
                        content_hash=canonical_sha256({"id": entry_id, "fields": field_map}),
                    )
                )

        self.upsert_entries(entries)
        return len(entries)
