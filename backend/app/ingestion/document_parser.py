"""Sandboxed deterministic multi-format document parser (PDF, MD, TXT, HTML, JSON, YAML, CSV)."""

from __future__ import annotations

import argparse
import csv
import importlib
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import zlib
from collections.abc import Sequence
from html.parser import HTMLParser
from pathlib import Path
from typing import Literal, cast

import yaml

from app.ingestion.models import (
    DocumentSection,
    ExtractedTable,
    ParsedDocument,
    SourceCitation,
    SourceKind,
    canonical_sha256,
    slugify_anchor,
)

DEFAULT_MAX_FILE_BYTES = 25 * 1024 * 1024
DEFAULT_PARSE_TIMEOUT_SECONDS = 15.0

_MD_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_MD_FENCE_RE = re.compile(r"^\s*(```|~~~)")
_MD_SEP_CELL_RE = re.compile(r"^:?-{3,}:?$")
_TXT_UNDERLINE_EQ_RE = re.compile(r"^={3,}\s*$")
_TXT_UNDERLINE_DASH_RE = re.compile(r"^-{3,}\s*$")
_TXT_NUMBERED_RE = re.compile(r"^(\d+(?:\.\d+){0,3})[.)]\s+([A-Z0-9][^\n]{1,80})$")
_HIDDEN_STYLE_RE = re.compile(r"display\s*:\s*none|visibility\s*:\s*hidden", re.IGNORECASE)

_PDF_OBJ_RE = re.compile(rb"(\d+)\s+\d+\s+obj\b(.*?)endobj", re.DOTALL)
_PDF_STREAM_RE = re.compile(rb"(<<.*?>>)\s*stream\r?\n(.*?)\r?\n?endstream", re.DOTALL)
_PDF_REF_RE = re.compile(rb"(\d+)\s+\d+\s+R")
_PDF_BT_BLOCK_RE = re.compile(rb"BT(.*?)ET", re.DOTALL)
_PDF_HEX_STR_RE = re.compile(rb"<([0-9A-Fa-f\s]+)>")

_SKIP_HTML_TAGS: frozenset[str] = frozenset(
    {"script", "style", "noscript", "nav", "footer", "aside", "iframe", "template", "svg"}
)
_VOID_HTML_TAGS: frozenset[str] = frozenset(
    {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "wbr"}
)
_BLOCK_HTML_TAGS: frozenset[str] = frozenset(
    {"p", "div", "li", "blockquote", "pre", "section", "article", "header", "dd", "dt"}
)

_EXT_TO_KIND: dict[str, SourceKind] = {
    ".md": "markdown",
    ".markdown": "markdown",
    ".txt": "txt",
    ".text": "txt",
    ".html": "html",
    ".htm": "html",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".csv": "csv",
    ".pdf": "pdf",
}


class DocumentParseError(Exception):
    """Structured error raised when document extraction violates limits or fails parsing."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")


def _collapse_excerpt(text: str, limit: int = 240) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 3] + "..."


def _unique_anchor(base: str, seen_anchors: dict[str, int]) -> str:
    count = seen_anchors.get(base, 0) + 1
    seen_anchors[base] = count
    if count == 1:
        return base
    return f"{base}-{count}"


def _update_heading_stack(
    stack: list[tuple[int, str]], level: int, heading: str
) -> tuple[str, ...]:
    while stack and stack[-1][0] >= level:
        stack.pop()
    stack.append((level, heading))
    return tuple(item for _, item in stack)


def _split_pipe_row(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def _is_gfm_separator(line: str, expected_cols: int) -> bool:
    if "|" not in line:
        return False
    cells = _split_pipe_row(line)
    if len(cells) != expected_cols or expected_cols == 0:
        return False
    return all(_MD_SEP_CELL_RE.match(cell) for cell in cells)


def _normalize_row(cells: Sequence[str], width: int) -> tuple[str, ...]:
    padded = list(cells[:width])
    while len(padded) < width:
        padded.append("")
    return tuple(padded)


def parse_markdown(
    text: str,
    *,
    source_name: str,
    url: str | None = None,
) -> ParsedDocument:
    """Parse Markdown text into hierarchical sections, heading anchors, and GFM tables."""
    lines = text.splitlines()
    sections: list[DocumentSection] = []
    all_tables: list[ExtractedTable] = []
    seen_anchors: dict[str, int] = {}
    heading_stack: list[tuple[int, str]] = []

    current_heading = ""
    current_level = 1
    current_anchor = "section"
    current_path: tuple[str, ...] = ()
    body_lines: list[str] = []
    section_tables: list[ExtractedTable] = []
    sec_counter = 0
    tbl_counter = 0
    in_fence = False

    def _flush_section() -> None:
        nonlocal sec_counter
        body_text = "\n".join(body_lines).strip()
        if not current_heading and not body_text and not section_tables:
            return
        sec_counter += 1
        heading_label = current_heading or source_name
        path = current_path or (heading_label,)
        anchor_val = _unique_anchor(current_anchor if current_heading else "intro", seen_anchors)
        sections.append(
            DocumentSection(
                section_id=f"sec_{sec_counter:04d}",
                heading=heading_label,
                level=current_level,
                anchor=anchor_val,
                heading_path=path,
                body=body_text,
                url=url,
                tables=tuple(section_tables),
                content_hash=canonical_sha256(
                    {"heading": heading_label, "body": body_text, "tables": len(section_tables)}
                ),
            )
        )

    idx = 0
    total_lines = len(lines)
    while idx < total_lines:
        line = lines[idx]
        if _MD_FENCE_RE.match(line):
            in_fence = not in_fence
            body_lines.append(line)
            idx += 1
            continue

        if not in_fence:
            heading_match = _MD_HEADING_RE.match(line)
            if heading_match:
                _flush_section()
                body_lines = []
                section_tables = []
                current_level = len(heading_match.group(1))
                current_heading = heading_match.group(2).strip()
                current_anchor = slugify_anchor(current_heading)
                current_path = _update_heading_stack(heading_stack, current_level, current_heading)
                idx += 1
                continue

            if (
                "|" in line
                and idx + 1 < total_lines
                and _is_gfm_separator(lines[idx + 1], len(_split_pipe_row(line)))
            ):
                headers = tuple(_split_pipe_row(line))
                width = len(headers)
                idx += 2
                rows: list[tuple[str, ...]] = []
                raw_table_lines = [line, lines[idx - 1]]
                while idx < total_lines and "|" in lines[idx] and lines[idx].strip():
                    raw_row = lines[idx]
                    raw_table_lines.append(raw_row)
                    rows.append(_normalize_row(_split_pipe_row(raw_row), width))
                    idx += 1
                tbl_counter += 1
                table_anchor = current_anchor if current_heading else None
                tbl = ExtractedTable(
                    table_id=f"tbl_{tbl_counter:04d}",
                    title=current_heading or f"Table {tbl_counter}",
                    headers=headers,
                    rows=tuple(rows),
                    citation=SourceCitation(
                        source_name=source_name,
                        source_kind="markdown",
                        url=url,
                        anchor=table_anchor,
                        heading_path=current_path
                        or ((current_heading,) if current_heading else ()),
                        excerpt=_collapse_excerpt(" ".join(raw_table_lines)),
                    ),
                )
                section_tables.append(tbl)
                all_tables.append(tbl)
                body_lines.extend(raw_table_lines)
                continue

        body_lines.append(line)
        idx += 1

    _flush_section()
    title = sections[0].heading if sections else source_name
    return ParsedDocument(
        doc_id=f"doc_{canonical_sha256((source_name, 'markdown', text))[:12]}",
        source_name=source_name,
        source_kind="markdown",
        title=title,
        raw_text=text.strip(),
        sections=tuple(sections),
        tables=tuple(all_tables),
        content_hash=canonical_sha256(text),
    )


def _looks_like_uppercase_heading(lines: Sequence[str], idx: int) -> bool:
    line = lines[idx].strip()
    if len(line) < 3 or len(line) > 70 or line.endswith("."):
        return False
    alpha_chars = [ch for ch in line if ch.isalpha()]
    if len(alpha_chars) < 3 or not all(ch.isupper() for ch in alpha_chars):
        return False
    prev_blank = idx == 0 or not lines[idx - 1].strip()
    next_blank = idx + 1 >= len(lines) or not lines[idx + 1].strip()
    return prev_blank or next_blank


def parse_text(
    text: str,
    *,
    source_name: str,
    url: str | None = None,
) -> ParsedDocument:
    """Parse plain TXT documents into sections via setext underlines, numbering, or headings."""
    lines = text.splitlines()
    sections: list[DocumentSection] = []
    seen_anchors: dict[str, int] = {}
    heading_stack: list[tuple[int, str]] = []

    current_heading = ""
    current_level = 1
    current_path: tuple[str, ...] = ()
    body_lines: list[str] = []
    sec_counter = 0

    def _flush() -> None:
        nonlocal sec_counter
        body_text = "\n".join(body_lines).strip()
        if not current_heading and not body_text:
            return
        sec_counter += 1
        label = current_heading or source_name
        anchor = _unique_anchor(slugify_anchor(label), seen_anchors)
        sections.append(
            DocumentSection(
                section_id=f"sec_{sec_counter:04d}",
                heading=label,
                level=current_level,
                anchor=anchor,
                heading_path=current_path or (label,),
                body=body_text,
                url=url,
                content_hash=canonical_sha256({"heading": label, "body": body_text}),
            )
        )

    idx = 0
    total_lines = len(lines)
    while idx < total_lines:
        line = lines[idx]
        if idx + 1 < total_lines and line.strip():
            next_line = lines[idx + 1]
            if _TXT_UNDERLINE_EQ_RE.match(next_line) or _TXT_UNDERLINE_DASH_RE.match(next_line):
                _flush()
                body_lines = []
                current_level = 1 if _TXT_UNDERLINE_EQ_RE.match(next_line) else 2
                current_heading = line.strip()
                current_path = _update_heading_stack(heading_stack, current_level, current_heading)
                idx += 2
                continue

        num_match = _TXT_NUMBERED_RE.match(line.strip())
        if num_match:
            _flush()
            body_lines = []
            dots = num_match.group(1).count(".") + 1
            current_level = min(6, dots)
            current_heading = line.strip()
            current_path = _update_heading_stack(heading_stack, current_level, current_heading)
            idx += 1
            continue

        if _looks_like_uppercase_heading(lines, idx):
            _flush()
            body_lines = []
            current_level = 1
            current_heading = line.strip()
            current_path = _update_heading_stack(heading_stack, current_level, current_heading)
            idx += 1
            continue

        body_lines.append(line)
        idx += 1

    _flush()
    title = sections[0].heading if sections else source_name
    return ParsedDocument(
        doc_id=f"doc_{canonical_sha256((source_name, 'txt', text))[:12]}",
        source_name=source_name,
        source_kind="txt",
        title=title,
        raw_text=text.strip(),
        sections=tuple(sections),
        tables=(),
        content_hash=canonical_sha256(text),
    )


class _DomNodeParser(HTMLParser):
    """Pure-stdlib HTML AST extractor stripping scripts, chrome, and hidden nodes."""

    def __init__(self, *, source_name: str, url: str | None) -> None:
        super().__init__(convert_charrefs=True)
        self.source_name = source_name
        self.url = url
        self.doc_title = ""
        self._in_title = False
        self._skip_depth = 0
        self._tag_skip_stack: list[tuple[str, bool]] = []
        self._seen_anchors: dict[str, int] = {}
        self._heading_stack: list[tuple[int, str]] = []

        self._active_heading_level: int | None = None
        self._active_heading_id: str | None = None
        self._heading_buf: list[str] = []

        self._current_heading = ""
        self._current_level = 1
        self._current_anchor = "section"
        self._current_path: tuple[str, ...] = ()
        self._body_buf: list[str] = []
        self._sec_tables: list[ExtractedTable] = []

        self._in_table = False
        self._table_title_buf: list[str] = []
        self._in_caption = False
        self._table_rows: list[list[str]] = []
        self._current_row: list[str] | None = None
        self._in_cell = False
        self._cell_buf: list[str] = []

        self.sections: list[DocumentSection] = []
        self.all_tables: list[ExtractedTable] = []
        self._sec_counter = 0
        self._tbl_counter = 0

    def _is_hidden_attrs(self, attr_map: dict[str, str | None]) -> bool:
        if "hidden" in attr_map:
            return True
        aria_hidden = attr_map.get("aria-hidden")
        if aria_hidden is not None and aria_hidden.strip().lower() == "true":
            return True
        style = attr_map.get("style") or ""
        return bool(_HIDDEN_STYLE_RE.search(style))

    def flush_current_section(self) -> None:
        body_text = re.sub(r"\n{3,}", "\n\n", "".join(self._body_buf)).strip()
        if not self._current_heading and not body_text and not self._sec_tables:
            return
        self._sec_counter += 1
        heading_label = self._current_heading or self.doc_title or self.source_name
        anchor_val = _unique_anchor(
            self._current_anchor if self._current_heading else "intro",
            self._seen_anchors,
        )
        path = self._current_path or (heading_label,)
        self.sections.append(
            DocumentSection(
                section_id=f"sec_{self._sec_counter:04d}",
                heading=heading_label,
                level=self._current_level,
                anchor=anchor_val,
                heading_path=path,
                body=body_text,
                url=self.url,
                tables=tuple(self._sec_tables),
                content_hash=canonical_sha256(
                    {"heading": heading_label, "body": body_text, "tables": len(self._sec_tables)}
                ),
            )
        )

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lower = tag.lower()
        attr_map = {k.lower(): v for k, v in attrs}
        hidden_or_skip = lower in _SKIP_HTML_TAGS or self._is_hidden_attrs(attr_map)
        if lower not in _VOID_HTML_TAGS:
            self._tag_skip_stack.append((lower, hidden_or_skip))
        if hidden_or_skip:
            if lower not in _VOID_HTML_TAGS:
                self._skip_depth += 1
            return
        if self._skip_depth > 0:
            return

        if lower == "title":
            self._in_title = True
        elif lower in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self._active_heading_level = int(lower[1])
            self._active_heading_id = attr_map.get("id")
            self._heading_buf = []
        elif lower == "table":
            self._in_table = True
            self._table_title_buf = []
            self._table_rows = []
        elif lower == "caption" and self._in_table:
            self._in_caption = True
        elif lower == "tr" and self._in_table:
            self._current_row = []
        elif lower in {"th", "td"} and self._current_row is not None:
            self._in_cell = True
            self._cell_buf = []
        elif lower == "br":
            self._body_buf.append("\n")

    def handle_endtag(self, tag: str) -> None:
        lower = tag.lower()
        if lower in _VOID_HTML_TAGS:
            return

        skipped_here = False
        for idx in range(len(self._tag_skip_stack) - 1, -1, -1):
            stacked_tag, _was_skipped = self._tag_skip_stack[idx]
            if stacked_tag == lower:
                _, skipped_here = self._tag_skip_stack.pop(idx)
                break
        if skipped_here:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if self._skip_depth > 0:
            return

        if lower == "title":
            self._in_title = False
        elif (
            lower in {"h1", "h2", "h3", "h4", "h5", "h6"} and self._active_heading_level is not None
        ):
            heading_text = " ".join("".join(self._heading_buf).split())
            if heading_text:
                self.flush_current_section()
                self._body_buf = []
                self._sec_tables = []
                self._current_level = self._active_heading_level
                self._current_heading = heading_text
                raw_id = (self._active_heading_id or "").strip()
                self._current_anchor = raw_id or slugify_anchor(heading_text)
                self._current_path = _update_heading_stack(
                    self._heading_stack, self._current_level, heading_text
                )
            self._active_heading_level = None
            self._active_heading_id = None
            self._heading_buf = []
        elif lower == "caption" and self._in_table:
            self._in_caption = False
        elif lower in {"th", "td"} and self._in_cell and self._current_row is not None:
            self._current_row.append(" ".join("".join(self._cell_buf).split()))
            self._in_cell = False
            self._cell_buf = []
        elif lower == "tr" and self._in_table and self._current_row is not None:
            if any(cell for cell in self._current_row):
                self._table_rows.append(self._current_row)
            self._current_row = None
        elif lower == "table" and self._in_table:
            if self._table_rows:
                self._tbl_counter += 1
                width = max(len(row) for row in self._table_rows)
                headers = _normalize_row(self._table_rows[0], width)
                rows = tuple(_normalize_row(row, width) for row in self._table_rows[1:])
                caption_txt = " ".join("".join(self._table_title_buf).split())
                tbl_title = caption_txt or self._current_heading or f"Table {self._tbl_counter}"
                flat_preview = (
                    " | ".join(headers) + "; " + "; ".join(" | ".join(r) for r in rows[:3])
                )
                tbl = ExtractedTable(
                    table_id=f"tbl_{self._tbl_counter:04d}",
                    title=tbl_title,
                    headers=headers,
                    rows=rows,
                    citation=SourceCitation(
                        source_name=self.source_name,
                        source_kind="html",
                        url=self.url,
                        anchor=self._current_anchor if self._current_heading else None,
                        heading_path=self._current_path
                        or ((self._current_heading,) if self._current_heading else ()),
                        excerpt=_collapse_excerpt(flat_preview),
                    ),
                )
                self._sec_tables.append(tbl)
                self.all_tables.append(tbl)
                self._body_buf.append("\n" + " | ".join(headers) + "\n")
                for row in rows:
                    self._body_buf.append(" | ".join(row) + "\n")
            self._in_table = False
            self._table_rows = []
            self._table_title_buf = []
        elif lower in _BLOCK_HTML_TAGS:
            self._body_buf.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return
        if self._in_title:
            self.doc_title += data
        elif self._active_heading_level is not None:
            self._heading_buf.append(data)
        elif self._in_caption:
            self._table_title_buf.append(data)
        elif self._in_cell:
            self._cell_buf.append(data)
        else:
            collapsed = re.sub(r"[ \t]+", " ", data)
            if collapsed.strip():
                self._body_buf.append(collapsed.strip() + " ")


def parse_html(
    html_text: str,
    *,
    source_name: str,
    url: str | None = None,
) -> ParsedDocument:
    """Parse HTML while stripping scripts, styles, chrome, and hidden DOM elements."""
    parser = _DomNodeParser(source_name=source_name, url=url)
    parser.feed(html_text)
    parser.close()
    parser.flush_current_section()

    clean_raw = "\n\n".join(
        f"{sec.heading}\n{sec.body}".strip() for sec in parser.sections if sec.body or sec.heading
    )
    doc_title = parser.doc_title.strip() or (
        parser.sections[0].heading if parser.sections else source_name
    )
    return ParsedDocument(
        doc_id=f"doc_{canonical_sha256((source_name, 'html', html_text))[:12]}",
        source_name=source_name,
        source_kind="html",
        title=doc_title,
        raw_text=clean_raw,
        sections=tuple(parser.sections),
        tables=tuple(parser.all_tables),
        content_hash=canonical_sha256(html_text),
    )


def parse_csv(
    csv_text: str,
    *,
    source_name: str,
    url: str | None = None,
) -> ParsedDocument:
    """Parse CSV text into an ExtractedTable and normalized section summary."""
    reader = csv.reader(io.StringIO(csv_text))
    raw_rows = [
        [cell.strip() for cell in row] for row in reader if any(cell.strip() for cell in row)
    ]
    if not raw_rows:
        return ParsedDocument(
            doc_id=f"doc_{canonical_sha256((source_name, 'csv', csv_text))[:12]}",
            source_name=source_name,
            source_kind="csv",
            title=source_name,
            raw_text="",
            sections=(),
            tables=(),
            content_hash=canonical_sha256(csv_text),
        )

    width = max(len(row) for row in raw_rows)
    headers = _normalize_row(raw_rows[0], width)
    rows = tuple(_normalize_row(row, width) for row in raw_rows[1:])
    citation = SourceCitation(
        source_name=source_name,
        source_kind="csv",
        url=url,
        heading_path=(source_name,),
        excerpt=_collapse_excerpt(" | ".join(headers)),
    )
    table = ExtractedTable(
        table_id="tbl_0001",
        title=source_name,
        headers=headers,
        rows=rows,
        citation=citation,
    )
    row_lines = [" | ".join(headers)]
    row_lines.extend(" | ".join(r) for r in rows)
    body = "\n".join(row_lines)
    section = DocumentSection(
        section_id="sec_0001",
        heading=source_name,
        level=1,
        anchor=slugify_anchor(source_name),
        heading_path=(source_name,),
        body=body,
        url=url,
        tables=(table,),
        content_hash=canonical_sha256(body),
    )
    return ParsedDocument(
        doc_id=f"doc_{canonical_sha256((source_name, 'csv', csv_text))[:12]}",
        source_name=source_name,
        source_kind="csv",
        title=source_name,
        raw_text=body,
        sections=(section,),
        tables=(table,),
        content_hash=canonical_sha256(csv_text),
    )


def parse_structured_text(
    raw_text: str,
    *,
    source_name: str,
    source_kind: Literal["json", "yaml"],
    url: str | None = None,
) -> ParsedDocument:
    """Parse JSON or YAML text deterministically into normalized document sections."""
    try:
        parsed_obj: object = (
            json.loads(raw_text) if source_kind == "json" else yaml.safe_load(raw_text)
        )
    except (json.JSONDecodeError, yaml.YAMLError) as exc:
        raise DocumentParseError(
            "RPG-E3003", f"Malformed {source_kind.upper()} in '{source_name}': {exc}"
        ) from exc

    canonical_text = json.dumps(parsed_obj, indent=2, sort_keys=True, default=str)
    sections: list[DocumentSection] = []
    if isinstance(parsed_obj, dict):
        typed_map = cast(dict[object, object], parsed_obj)
        seen_anchors: dict[str, int] = {}
        for idx, key in enumerate(sorted(typed_map, key=lambda item: str(item)), start=1):
            key_str = str(key)
            val_text = json.dumps(typed_map[key], indent=2, sort_keys=True, default=str)
            sections.append(
                DocumentSection(
                    section_id=f"sec_{idx:04d}",
                    heading=key_str,
                    level=1,
                    anchor=_unique_anchor(slugify_anchor(key_str), seen_anchors),
                    heading_path=(key_str,),
                    body=val_text,
                    url=url,
                    content_hash=canonical_sha256(val_text),
                )
            )
    else:
        sections.append(
            DocumentSection(
                section_id="sec_0001",
                heading=source_name,
                level=1,
                anchor=slugify_anchor(source_name),
                heading_path=(source_name,),
                body=canonical_text,
                url=url,
                content_hash=canonical_sha256(canonical_text),
            )
        )

    return ParsedDocument(
        doc_id=f"doc_{canonical_sha256((source_name, source_kind, raw_text))[:12]}",
        source_name=source_name,
        source_kind=source_kind,
        title=source_name,
        raw_text=canonical_text,
        sections=tuple(sections),
        tables=(),
        content_hash=canonical_sha256(canonical_text),
    )


def _decode_pdf_literal_string(raw_bytes: bytes) -> str:
    out: list[str] = []
    idx = 0
    length = len(raw_bytes)
    escape_map = {
        ord("n"): "\n",
        ord("r"): "\r",
        ord("t"): "\t",
        ord("b"): "\b",
        ord("f"): "\f",
        ord("\\"): "\\",
        ord("("): "(",
        ord(")"): ")",
    }
    while idx < length:
        byte = raw_bytes[idx]
        if byte == ord("\\") and idx + 1 < length:
            nxt = raw_bytes[idx + 1]
            if nxt in escape_map:
                out.append(escape_map[nxt])
                idx += 2
                continue
            if nxt in (ord("\r"), ord("\n")):
                idx += 2
                if nxt == ord("\r") and idx < length and raw_bytes[idx] == ord("\n"):
                    idx += 1
                continue
            oct_digits: list[int] = []
            pos = idx + 1
            while pos < length and len(oct_digits) < 3 and ord("0") <= raw_bytes[pos] <= ord("7"):
                oct_digits.append(raw_bytes[pos])
                pos += 1
            if oct_digits:
                code_point = int(bytes(oct_digits).decode("ascii"), 8)
                out.append(chr(code_point))
                idx = pos
                continue
            out.append(chr(nxt))
            idx += 2
            continue
        out.append(bytes([byte]).decode("latin-1"))
        idx += 1
    return "".join(out)


def _decode_pdf_hex_string(hex_bytes: bytes) -> str:
    cleaned = re.sub(rb"\s+", b"", hex_bytes)
    if len(cleaned) % 2 == 1:
        cleaned += b"0"
    try:
        decoded = bytes.fromhex(cleaned.decode("ascii"))
    except ValueError:
        return ""
    if decoded.startswith(b"\xfe\xff"):
        return decoded[2:].decode("utf-16-be", errors="ignore")
    return decoded.decode("latin-1", errors="ignore")


def _extract_pdf_text_from_stream(stream_bytes: bytes) -> str:
    chunks: list[str] = []
    bt_blocks = _PDF_BT_BLOCK_RE.findall(stream_bytes) or [stream_bytes]
    for block in bt_blocks:
        idx = 0
        length = len(block)
        line_chunks: list[str] = []
        while idx < length:
            ch = block[idx]
            if ch == ord("("):
                idx += 1
                start = idx
                depth = 1
                while idx < length and depth > 0:
                    cur = block[idx]
                    if cur == ord("\\"):
                        idx += 2
                        continue
                    if cur == ord("("):
                        depth += 1
                    elif cur == ord(")"):
                        depth -= 1
                        if depth == 0:
                            break
                    idx += 1
                literal = _decode_pdf_literal_string(block[start:idx])
                if literal:
                    line_chunks.append(literal)
                idx += 1
                continue
            if ch == ord("<") and (idx + 1 >= length or block[idx + 1] != ord("<")):
                end = block.find(b">", idx + 1)
                if end != -1:
                    hex_txt = _decode_pdf_hex_string(block[idx + 1 : end])
                    if hex_txt:
                        line_chunks.append(hex_txt)
                    idx = end + 1
                    continue
            idx += 1
        joined = "".join(line_chunks).strip()
        if joined:
            chunks.append(joined)
    return "\n".join(chunks)


def _extract_pdf_pages_pure_python(raw_bytes: bytes) -> list[str]:
    stream_texts_by_obj: dict[int, str] = {}
    ordered_streams: list[str] = []
    page_contents_refs: list[list[int]] = []

    for obj_num_bytes, obj_body in _PDF_OBJ_RE.findall(raw_bytes):
        obj_num = int(obj_num_bytes)
        stream_match = _PDF_STREAM_RE.search(obj_body)
        if stream_match:
            header_dict, raw_stream = stream_match.group(1), stream_match.group(2)
            payload = raw_stream
            if b"/FlateDecode" in header_dict:
                try:
                    payload = zlib.decompress(raw_stream.strip(b"\r\n"))
                except zlib.error:
                    try:
                        payload = zlib.decompress(raw_stream)
                    except zlib.error:
                        payload = raw_stream
            extracted = _extract_pdf_text_from_stream(payload)
            if extracted.strip():
                stream_texts_by_obj[obj_num] = extracted.strip()
                ordered_streams.append(extracted.strip())
        elif re.search(rb"/Type\s*/Page\b(?!s)", obj_body):
            contents_match = re.search(rb"/Contents\s+(\[.*?\]|\d+\s+\d+\s+R)", obj_body, re.DOTALL)
            if contents_match:
                refs = [int(r) for r in _PDF_REF_RE.findall(contents_match.group(1))]
                if refs:
                    page_contents_refs.append(refs)

    if page_contents_refs:
        pages: list[str] = []
        for refs in page_contents_refs:
            parts = [stream_texts_by_obj[r] for r in refs if r in stream_texts_by_obj]
            pages.append("\n".join(parts).strip())
        if any(pages):
            return pages
    return ordered_streams


def _extract_pdf_pages_optional_libs(raw_bytes: bytes) -> list[str] | None:
    if importlib.util.find_spec("fitz") is not None:
        fitz_mod = importlib.import_module("fitz")
        doc = fitz_mod.open(stream=raw_bytes, filetype="pdf")
        try:
            return [str(page.get_text("text")).strip() for page in doc]
        finally:
            doc.close()
    if importlib.util.find_spec("pypdf") is not None:
        pypdf_mod = importlib.import_module("pypdf")
        reader = pypdf_mod.PdfReader(io.BytesIO(raw_bytes))
        return [(page.extract_text() or "").strip() for page in reader.pages]
    return None


def parse_pdf_bytes(
    raw_bytes: bytes,
    *,
    source_name: str,
    url: str | None = None,
) -> ParsedDocument:
    """Parse PDF bytes via optional PyMuPDF/pypdf fast-path or pure-Python FlateDecode fallback."""
    if not raw_bytes.lstrip().startswith(b"%PDF"):
        raise DocumentParseError("RPG-E3003", f"Invalid PDF header while parsing '{source_name}'.")

    pages = _extract_pdf_pages_optional_libs(raw_bytes)
    if pages is None:
        pages = _extract_pdf_pages_pure_python(raw_bytes)

    sections: list[DocumentSection] = []
    warnings: list[str] = []
    sec_counter = 0
    for page_idx, page_text in enumerate(pages, start=1):
        cleaned = page_text.strip()
        if not cleaned:
            continue
        first_line = next((ln.strip() for ln in cleaned.splitlines() if ln.strip()), "")
        heading = first_line[:80] if first_line else f"Page {page_idx}"
        sec_counter += 1
        sections.append(
            DocumentSection(
                section_id=f"sec_{sec_counter:04d}",
                heading=heading,
                level=1,
                anchor=f"page-{page_idx}",
                heading_path=(f"Page {page_idx}", heading),
                body=cleaned,
                page_number=page_idx,
                url=url,
                content_hash=canonical_sha256({"page": page_idx, "text": cleaned}),
            )
        )

    if not sections:
        warnings.append("PDF contained no extractable text streams (may be scanned images).")

    raw_text = "\n\n".join(sec.body for sec in sections)
    doc_title = sections[0].heading if sections else source_name
    return ParsedDocument(
        doc_id=f"doc_{canonical_sha256((source_name, 'pdf', raw_bytes))[:12]}",
        source_name=source_name,
        source_kind="pdf",
        title=doc_title,
        raw_text=raw_text,
        sections=tuple(sections),
        tables=(),
        content_hash=canonical_sha256(raw_bytes),
        warnings=tuple(warnings),
    )


def _parse_direct(
    raw_bytes: bytes,
    *,
    source_name: str,
    source_kind: SourceKind,
    url: str | None = None,
    max_bytes: int = DEFAULT_MAX_FILE_BYTES,
) -> ParsedDocument:
    if len(raw_bytes) > max_bytes:
        raise DocumentParseError(
            "RPG-E3002",
            f"Input '{source_name}' ({len(raw_bytes)} bytes) exceeds max {max_bytes} bytes.",
        )

    if source_kind == "pdf":
        return parse_pdf_bytes(raw_bytes, source_name=source_name, url=url)

    text = raw_bytes.decode("utf-8", errors="replace")
    if source_kind == "markdown":
        return parse_markdown(text, source_name=source_name, url=url)
    if source_kind == "txt":
        return parse_text(text, source_name=source_name, url=url)
    if source_kind == "html":
        return parse_html(text, source_name=source_name, url=url)
    if source_kind == "csv":
        return parse_csv(text, source_name=source_name, url=url)
    if source_kind in {"json", "yaml"}:
        return parse_structured_text(
            text,
            source_name=source_name,
            source_kind=cast(Literal["json", "yaml"], source_kind),
            url=url,
        )

    raise DocumentParseError(
        "RPG-E3003", f"Unsupported document source_kind '{source_kind}' for parser."
    )


def parse_document_bytes(
    raw_bytes: bytes,
    *,
    source_name: str,
    source_kind: SourceKind,
    url: str | None = None,
    max_bytes: int = DEFAULT_MAX_FILE_BYTES,
    timeout_seconds: float = DEFAULT_PARSE_TIMEOUT_SECONDS,
    sandboxed: bool = True,
) -> ParsedDocument:
    """Parse raw bytes with strict size/time limits, sandboxed in a subprocess by default."""
    if len(raw_bytes) > max_bytes:
        raise DocumentParseError(
            "RPG-E3002",
            f"Input '{source_name}' ({len(raw_bytes)} bytes) exceeds max {max_bytes} bytes.",
        )
    if not sandboxed:
        return _parse_direct(
            raw_bytes,
            source_name=source_name,
            source_kind=source_kind,
            url=url,
            max_bytes=max_bytes,
        )

    cmd = [
        sys.executable,
        "-m",
        "app.ingestion.document_parser",
        "--source-kind",
        source_kind,
        "--source-name",
        source_name,
        "--max-bytes",
        str(max_bytes),
    ]
    if url is not None:
        cmd.extend(["--url", url])

    safe_env = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUNBUFFERED": "1",
    }
    backend_root = Path(__file__).resolve().parents[2]
    try:
        proc = subprocess.run(
            cmd,
            input=raw_bytes,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
            cwd=str(backend_root),
            env=safe_env,
        )
    except subprocess.TimeoutExpired as exc:
        raise DocumentParseError(
            "RPG-E3001", f"Document parsing timed out after {timeout_seconds}s for '{source_name}'."
        ) from exc

    if proc.returncode != 0:
        err_text = proc.stderr.decode("utf-8", errors="replace").strip()
        try:
            err_payload = json.loads(err_text)
            if isinstance(err_payload, dict) and "code" in err_payload and "message" in err_payload:
                raise DocumentParseError(str(err_payload["code"]), str(err_payload["message"]))
        except json.JSONDecodeError:
            pass
        raise DocumentParseError(
            "RPG-E3003", f"Sandboxed parser failed for '{source_name}': {err_text}"
        )

    return ParsedDocument.model_validate_json(proc.stdout.decode("utf-8"))


def parse_document_file(
    path: Path,
    *,
    sandboxed: bool = True,
    max_bytes: int = DEFAULT_MAX_FILE_BYTES,
    timeout_seconds: float = DEFAULT_PARSE_TIMEOUT_SECONDS,
) -> ParsedDocument:
    """Detect file type by extension, enforce size bounds before reading, and parse."""
    suffix = path.suffix.lower()
    source_kind = _EXT_TO_KIND.get(suffix)
    if source_kind is None:
        raise DocumentParseError(
            "RPG-E3003", f"Unsupported file extension '{path.suffix}' on '{path.name}'."
        )
    file_size = path.stat().st_size
    if file_size > max_bytes:
        raise DocumentParseError(
            "RPG-E3002",
            f"File '{path.name}' ({file_size} bytes) exceeds max limit of {max_bytes} bytes.",
        )
    raw_bytes = path.read_bytes()
    return parse_document_bytes(
        raw_bytes,
        source_name=path.name,
        source_kind=source_kind,
        max_bytes=max_bytes,
        timeout_seconds=timeout_seconds,
        sandboxed=sandboxed,
    )


def main(argv: list[str] | None = None) -> int:
    """Subprocess entrypoint reading raw document bytes from stdin and emitting JSON AST."""
    parser = argparse.ArgumentParser(description="Sandboxed Meddah document parser worker.")
    parser.add_argument("--source-kind", required=True)
    parser.add_argument("--source-name", required=True)
    parser.add_argument("--url", default=None)
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_FILE_BYTES)
    args = parser.parse_args(argv)

    raw_bytes = sys.stdin.buffer.read()
    try:
        doc = _parse_direct(
            raw_bytes,
            source_name=args.source_name,
            source_kind=cast(SourceKind, args.source_kind),
            url=args.url,
            max_bytes=args.max_bytes,
        )
    except DocumentParseError as exc:
        print(json.dumps({"code": exc.code, "message": exc.message}), file=sys.stderr)
        return 2
    sys.stdout.write(doc.model_dump_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
