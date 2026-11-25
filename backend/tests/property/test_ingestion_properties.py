"""Hypothesis property tests for deterministic Phase 2A ingestion invariants."""

from __future__ import annotations

import ipaddress

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.ingestion import (
    CompendiumEntry,
    CompendiumIndex,
    SourceCitation,
    SsrfBlockedError,
    canonical_sha256,
    parse_markdown,
    validate_url_target,
)


@pytest.mark.zero_ai
@settings(max_examples=30)
@given(
    heading=st.text(
        alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters=" -_"),
        min_size=1,
        max_size=40,
    ).filter(lambda s: s.strip() != ""),
    cell_a=st.text(
        alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters=" "),
        min_size=1,
        max_size=20,
    ).filter(lambda s: s.strip() != ""),
    cell_b=st.text(
        alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters=" "),
        min_size=1,
        max_size=20,
    ).filter(lambda s: s.strip() != ""),
)
def test_markdown_parse_determinism_and_anchor_invariant(
    heading: str,
    cell_a: str,
    cell_b: str,
) -> None:
    """Parsing arbitrary valid Markdown headings and GFM tables is 100% deterministic."""
    md = (
        f"# {heading.strip()}\n\nBody details.\n\n"
        "| col_a | col_b |\n"
        "| --- | --- |\n"
        f"| {cell_a.strip()} | {cell_b.strip()} |\n"
    )
    first = parse_markdown(md, source_name="prop.md")
    second = parse_markdown(md, source_name="prop.md")
    assert first.content_hash == second.content_hash
    assert len(first.sections) >= 1
    assert first.sections[0].anchor != ""
    assert len(first.tables) == 1


@pytest.mark.zero_ai
@settings(max_examples=40)
@given(query=st.text(min_size=0, max_size=80))
def test_fts5_search_never_crashes_on_arbitrary_query_strings(query: str) -> None:
    """FTS5 sanitizer safely handles any Unicode, punctuation, or boolean keywords."""
    with CompendiumIndex() as index:
        index.upsert_entry(
            CompendiumEntry(
                entry_id="e_1",
                category="rule_note",
                title="Sample Rule",
                body="Deterministic resolution check mechanic.",
                tags=("core",),
                citation=SourceCitation(source_name="prop.md", source_kind="markdown"),
                content_hash=canonical_sha256("e_1"),
            )
        )
        hits = index.search(query)
        assert isinstance(hits, tuple)


def _ip_disallowed(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    ):
        return True
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped is not None:
        return _ip_disallowed(addr.ipv4_mapped)
    return False


@pytest.mark.zero_ai
@settings(max_examples=40)
@given(raw_ip=st.ip_addresses())
def test_ssrf_blocks_every_non_global_ip_literal(
    raw_ip: ipaddress.IPv4Address | ipaddress.IPv6Address,
) -> None:
    """Every non-public IPv4 or IPv6 literal is rejected by validate_url_target."""
    host_str = f"[{raw_ip}]" if isinstance(raw_ip, ipaddress.IPv6Address) else str(raw_ip)
    url = f"https://{host_str}/rules"
    if _ip_disallowed(raw_ip):
        with pytest.raises(SsrfBlockedError):
            validate_url_target(url)
    else:
        assert validate_url_target(url) == url
