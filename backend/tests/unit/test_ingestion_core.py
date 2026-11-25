"""Unit tests for Phase 2A ingestion parsers, FTS5 index, deterministic importer & JIT compiler."""

from __future__ import annotations

import json
import stat
import zipfile
import zlib
from pathlib import Path

import pytest

from app.ingestion import (
    MODULE_MANIFEST,
    CompendiumEntry,
    CompendiumIndex,
    DocumentParseError,
    IngestionValidationError,
    JitBlockCompiler,
    SourceCitation,
    canonical_sha256,
    import_ruleset_data,
    import_ruleset_file,
    import_structured_tables,
    ingest_document_deterministically,
    parse_document_bytes,
    parse_document_file,
    safe_extract_ruleset_archive,
)
from app.ruleset_vm import (
    ActionBlock,
    ConditionBlock,
    EntityState,
    FormBlock,
    ModuleOverrideEvent,
    ModuleRegistry,
    RulesetSchema,
    VmEvent,
    apply_event,
    initialize_scene_state,
    replay_events,
    state_hash,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
SAMPLE_RULESETS_DIR = REPO_ROOT / "sample_rulesets"

SEVEN_RULESET_PATHS: tuple[Path, ...] = (
    SAMPLE_RULESETS_DIR / "showcase" / "classic_d20_fantasy" / "ruleset.json",
    SAMPLE_RULESETS_DIR / "showcase" / "grimdark_d100_investigative" / "ruleset.json",
    SAMPLE_RULESETS_DIR / "showcase" / "narrative_2d6_clocks" / "ruleset.json",
    SAMPLE_RULESETS_DIR / "conformance" / "dice_pool_successes" / "ruleset.json",
    SAMPLE_RULESETS_DIR / "conformance" / "step_symbol_dice" / "ruleset.json",
    SAMPLE_RULESETS_DIR / "conformance" / "resource_wager_card_draw" / "ruleset.json",
    SAMPLE_RULESETS_DIR / "conformance" / "rules_light_narrative" / "ruleset.json",
)


def _build_minimal_two_page_pdf(page1_text: str, page2_text: str) -> bytes:
    """Build a valid minimal 2-page PDF (page 1 uncompressed, page 2 FlateDecode compressed)."""
    stream1 = f"BT\n({page1_text}) Tj\nET\n".encode("latin-1")
    stream2_plain = f"BT\n[({page2_text}) -20 (!!)] TJ\nET\n".encode("latin-1")
    stream2_zip = zlib.compress(stream2_plain)

    objects: list[bytes] = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R 5 0 R] /Count 2 >>\nendobj\n",
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /Contents 4 0 R >>\nendobj\n",
        (
            f"4 0 obj\n<< /Length {len(stream1)} >>\nstream\n".encode("ascii")
            + stream1
            + b"\nendstream\nendobj\n"
        ),
        b"5 0 obj\n<< /Type /Page /Parent 2 0 R /Contents 6 0 R >>\nendobj\n",
        (
            f"6 0 obj\n<< /Filter /FlateDecode /Length {len(stream2_zip)} >>\nstream\n".encode(
                "ascii"
            )
            + stream2_zip
            + b"\nendstream\nendobj\n"
        ),
    ]
    buf = bytearray(b"%PDF-1.4\n")
    for obj in objects:
        buf.extend(obj)
    buf.extend(b"%%EOF\n")
    return bytes(buf)


@pytest.mark.zero_ai
def test_ingestion_manifest_availability_and_toggle_round_trip() -> None:
    """Verify ingestion_studio manifest registers cleanly, is available, and preserves replay."""
    light_rs = RulesetSchema.model_validate_json(
        (SAMPLE_RULESETS_DIR / "conformance" / "rules_light_narrative" / "ruleset.json").read_text(
            encoding="utf-8"
        )
    )
    registry = ModuleRegistry()
    registry.register(MODULE_MANIFEST)
    snapshot = registry.resolve_status("ingestion_studio", light_rs.declared_primitives)
    assert snapshot.state == "available"

    ent = EntityState(entity_id="pc_1", name="Hero", tags=("traveler",))
    scene = initialize_scene_state(light_rs, "srd_lab", [ent], active_modules=())

    evt_on = ModuleOverrideEvent(
        module_id="ingestion_studio",
        enabled=True,
        actor_seat_id="host",
    )
    vm_on = VmEvent(
        event_id="evt_1",
        event_type="MODULE_OVERRIDE",
        actor_id="host",
        payload=evt_on.model_dump(mode="json"),
    )
    vm_off = VmEvent(
        event_id="evt_2",
        event_type="MODULE_OVERRIDE",
        actor_id="host",
        payload=evt_on.model_copy(update={"enabled": False}).model_dump(mode="json"),
    )
    vm_on2 = VmEvent(
        event_id="evt_3",
        event_type="MODULE_OVERRIDE",
        actor_id="host",
        payload=evt_on.model_dump(mode="json"),
    )
    step1 = apply_event(light_rs, scene, vm_on)
    step2 = apply_event(light_rs, step1, vm_off)
    final_live = apply_event(light_rs, step2, vm_on2)
    final_replayed = replay_events(light_rs, scene, (vm_on, vm_off, vm_on2))
    assert final_live.active_modules == ("ingestion_studio",)
    assert state_hash(final_live) == state_hash(final_replayed)


@pytest.mark.zero_ai
def test_sandboxed_parsers_across_all_formats_and_limits(tmp_path: Path) -> None:
    """Verify sandboxed subprocess parsing across MD, TXT, HTML, JSON, YAML, CSV, PDF & limits."""
    md_text = (
        "# Core Rules\n\nIntro paragraph.\n\n"
        "## Actions Table\n"
        "| action_id | label | category |\n"
        "| --- | --- | --- |\n"
        "| lunge | Quick Lunge | action |\n"
    )
    md_doc = parse_document_bytes(
        md_text.encode("utf-8"),
        source_name="core.md",
        source_kind="markdown",
        sandboxed=True,
    )
    assert len(md_doc.sections) == 2
    assert md_doc.sections[1].anchor == "actions-table"
    assert md_doc.sections[1].heading_path == ("Core Rules", "Actions Table")
    assert len(md_doc.tables) == 1
    assert md_doc.tables[0].rows == (("lunge", "Quick Lunge", "action"),)

    txt_text = (
        "CORE SECTION\nFirst detail.\n\n1.2 Combat Step\n----------------\nRoll initiative.\n"
    )
    txt_doc = parse_document_bytes(
        txt_text.encode("utf-8"), source_name="notes.txt", source_kind="txt", sandboxed=True
    )
    assert [sec.heading for sec in txt_doc.sections] == ["CORE SECTION", "1.2 Combat Step"]

    html_text = (
        "<html><head><title>SRD</title><style>.x{}</style><script>evil()</script></head>"
        "<body><nav>Menu Skip</nav>"
        "<div hidden>Hidden secret</div>"
        "<div style='display:none'>Invisible div</div>"
        "<h1 id='combat-sec'>Combat Basics</h1><p>Strike foes cleanly.</p>"
        "<table><tr><th>Name</th><th>Cost</th></tr><tr><td>Parry</td><td>1</td></tr></table>"
        "<footer>Footer Skip</footer></body></html>"
    )
    html_doc = parse_document_bytes(
        html_text.encode("utf-8"),
        source_name="srd.html",
        source_kind="html",
        url="https://example.org/srd.html",
        sandboxed=True,
    )
    assert "evil()" not in html_doc.raw_text
    assert "Hidden secret" not in html_doc.raw_text
    assert "Invisible div" not in html_doc.raw_text
    assert "Menu Skip" not in html_doc.raw_text
    assert "Footer Skip" not in html_doc.raw_text
    assert html_doc.sections[0].anchor == "combat-sec"
    assert len(html_doc.tables) == 1
    assert html_doc.tables[0].citation.url == "https://example.org/srd.html"

    csv_path = tmp_path / "gear.csv"
    csv_path.write_text("item_id,label\nrope,Hemp Rope\ntorch,Pitch Torch\n", encoding="utf-8")
    csv_doc = parse_document_file(csv_path, sandboxed=True)
    assert len(csv_doc.tables) == 1
    assert len(csv_doc.tables[0].rows) == 2

    yaml_doc = parse_document_bytes(
        b"rules:\n  turn_limit: 5\n", source_name="rules.yaml", source_kind="yaml", sandboxed=True
    )
    assert yaml_doc.sections[0].heading == "rules"
    assert '"turn_limit": 5' in yaml_doc.raw_text

    json_doc = parse_document_bytes(
        b'{"clock": {"segments": 6}}', source_name="clock.json", source_kind="json", sandboxed=True
    )
    assert json_doc.sections[0].heading == "clock"

    with pytest.raises(DocumentParseError, match="Malformed JSON"):
        parse_document_bytes(
            b"{bad json", source_name="bad.json", source_kind="json", sandboxed=True
        )

    pdf_bytes = _build_minimal_two_page_pdf("Chapter One Overview", "Flate Page Two Rule")
    pdf_doc = parse_document_bytes(
        pdf_bytes, source_name="manual.pdf", source_kind="pdf", sandboxed=True
    )
    assert len(pdf_doc.sections) == 2
    assert pdf_doc.sections[0].page_number == 1
    assert "Chapter One Overview" in pdf_doc.sections[0].body
    assert pdf_doc.sections[1].page_number == 2
    assert "Flate Page Two Rule!!" in pdf_doc.sections[1].body

    # Size limit check (RPG-E3002) and timeout check (RPG-E3001)
    with pytest.raises(DocumentParseError, match="exceeds max"):
        parse_document_bytes(
            b"12345678901",
            source_name="big.txt",
            source_kind="txt",
            max_bytes=10,
            sandboxed=True,
        )
    with pytest.raises(DocumentParseError, match="timed out"):
        parse_document_bytes(
            b"short text",
            source_name="slow.txt",
            source_kind="txt",
            timeout_seconds=0.0001,
            sandboxed=True,
        )


@pytest.mark.zero_ai
def test_compendium_fts5_bm25_index_and_search(tmp_path: Path) -> None:
    """Verify FTS5 BM25 indexing, filtering, CRUD, WAL DB file persistence & query safety."""
    md = (
        "# Spells & Powers\n\nCast blazing bolts across rooms.\n\n"
        "## Bestiary\n"
        "| creature_id | label | traits |\n"
        "| --- | --- | --- |\n"
        "| dire_wolf | Dire Wolf | pack hunter wolf |\n"
        "| mist_hound | Mist Hound | ethereal tracker |\n"
    )
    doc = parse_document_bytes(
        md.encode("utf-8"), source_name="compendium.md", source_kind="markdown", sandboxed=False
    )

    db_file = tmp_path / "compendium.sqlite"
    with CompendiumIndex(db_file) as index:
        added = index.index_parsed_document(doc)
        assert added == 4
        assert index.count() == 4

        wolf_hits = index.search("wolf hunter")
        assert len(wolf_hits) >= 1
        assert any(
            hit.entry.title == "Dire Wolf"
            and hit.entry.category == "creature"
            and hit.entry.structured_fields.get("creature_id") == "dire_wolf"
            for hit in wolf_hits
        )

        # Punctuation / FTS5 operators in raw query string must never raise syntax errors
        punct_hits = index.search('AND OR NOT (wolf) ["*]:?!')
        assert len(punct_hits) >= 1

        # Category and tag filtering + CRUD lifecycle
        custom = CompendiumEntry(
            entry_id="custom_form_01",
            category="form",
            title="Silver Fox Form",
            body="property_mode=delta_overlay; agile scouts shape",
            tags=("shapeshift", "scout"),
            structured_fields={"property_mode": "delta_overlay"},
            citation=SourceCitation(source_name="manual.md", source_kind="markdown"),
            content_hash=canonical_sha256("custom_form_01"),
        )
        index.upsert_entry(custom)
        assert index.get_entry("custom_form_01") is not None
        assert len(index.list_entries(category="form", tag="scout")) == 1
        assert len(index.search("fox", category="form", tag="shapeshift")) == 1
        assert index.delete_entry("custom_form_01") is True
        assert index.get_entry("custom_form_01") is None


@pytest.mark.zero_ai
def test_deterministic_importer_seven_rulesets_archives_tables_and_heuristics(
    tmp_path: Path,
) -> None:
    """Verify deterministic import of all 7 fixtures, safe zip guards, tables & heuristics."""
    for path in SEVEN_RULESET_PATHS:
        ruleset, job = import_ruleset_file(path)
        assert ruleset.validate_graph() == []
        assert job.status == "ready_for_review"
        assert len(job.proposals) >= 2

    # Valid .rpgrules zip archive
    sample_data = SEVEN_RULESET_PATHS[-1].read_text(encoding="utf-8")
    good_zip = tmp_path / "good.rpgrules"
    with zipfile.ZipFile(good_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("ruleset.json", sample_data)
    rs_zip, _ = import_ruleset_file(good_zip)
    assert rs_zip.manifest.package_id == "rules_light_narrative"

    # Zip-slip path traversal rejection
    slip_zip = tmp_path / "slip.rpgrules"
    with zipfile.ZipFile(slip_zip, "w") as zf:
        zf.writestr("../escape.json", sample_data)
    with pytest.raises(DocumentParseError, match="path traversal"):
        safe_extract_ruleset_archive(slip_zip)

    # Zip-symlink rejection
    sym_zip = tmp_path / "symlink.rpgrules"
    with zipfile.ZipFile(sym_zip, "w") as zf:
        info = zipfile.ZipInfo("ruleset.json")
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        zf.writestr(info, sample_data)
    with pytest.raises(DocumentParseError, match="symbolic link"):
        safe_extract_ruleset_archive(sym_zip)

    # Zip-bomb compression ratio rejection (> 100:1)
    bomb_zip = tmp_path / "bomb.rpgrules"
    with zipfile.ZipFile(bomb_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("ruleset.json", b"A" * 500_000)
    with pytest.raises(DocumentParseError, match="compression ratio"):
        safe_extract_ruleset_archive(bomb_zip)

    # Structured Markdown-table ruleset compilation
    tables_md = (
        "# Properties\n"
        "| prop_id | label | default_value |\n"
        "| --- | --- | --- |\n"
        "| grit | Grit | 12 |\n\n"
        "# Resource Pools\n"
        "| pool_id | label | default_current | max_formula | track_segments |\n"
        "| --- | --- | --- | --- | --- |\n"
        "| resolve | Resolve | 8 | 8 | 8 |\n\n"
        "# Resolutions\n"
        "| mech_id | label | randomizer_kind | formula |\n"
        "| --- | --- | --- | --- |\n"
        "| quick_coin | Fate Flip | coin_flip | 1 |\n\n"
        "# Conditions\n"
        "| condition_id | label | blocks_tags |\n"
        "| --- | --- | --- |\n"
        "| rattled | Rattled | focus |\n\n"
        "# Actions\n"
        "| action_id | label | resolution_id | pool_costs | tags |\n"
        "| --- | --- | --- | --- | --- |\n"
        "| steady_aim | Steady Aim | quick_coin | resolve=1 | focus |\n\n"
        "# Forms\n"
        "| form_id | label | property_mode | property_values | granted_tags |\n"
        "| --- | --- | --- | --- | --- |\n"
        "| wolf_shape | Wolf Shape | replace_subset | grit=16 | beast |\n"
    )
    parsed_tables = parse_document_bytes(
        tables_md.encode("utf-8"), source_name="tables.md", source_kind="markdown", sandboxed=False
    )
    compiled_rs, staged_job = import_structured_tables(
        parsed_tables, package_id="table_sys", name="Table System"
    )
    assert compiled_rs.validate_graph() == []
    assert "wolf_shape" in compiled_rs.forms
    assert compiled_rs.resolutions["quick_coin"].randomizer.kind == "coin_flip"
    assert len(staged_job.proposals) == 6

    # Diff against modified ruleset + heuristic unstructured ingestion
    altered = compiled_rs.model_dump(mode="json")
    _, diff_job = import_ruleset_data(
        altered, source_name="same.json", existing_ruleset=compiled_rs
    )
    assert all(p.diff_status == "UNCHANGED" for p in diff_job.proposals)

    unstructured_md = (
        "# Coin Flip Fate Check\nFlip a coin to decide close calls.\n\n"
        "# Doom Clock Track\nAdvance the 6-segment clock whenever stealth breaks.\n\n"
        "# Raven Form\nShapeshift into a raven to scout rooftops.\n\n"
        "# Strike Action\nRoll 2d6+1 against guard.\n"
    )
    unstruct_doc = parse_document_bytes(
        unstructured_md.encode("utf-8"),
        source_name="prose.md",
        source_kind="markdown",
        sandboxed=False,
    )
    heuristic_job = ingest_document_deterministically(unstruct_doc, existing_ruleset=compiled_rs)
    categories = {p.block_category for p in heuristic_job.proposals}
    assert {"resolution", "resource_pool", "form", "action"}.issubset(categories)

    # Invalid structured schema error check
    with pytest.raises(IngestionValidationError):
        import_ruleset_data({"invalid": True}, source_name="bad.json")


@pytest.mark.zero_ai
def test_jit_block_compiler_and_cache_hits() -> None:
    """Verify deterministic JIT compilation into VM models and content-hash caching."""
    rs_data = json.loads(SEVEN_RULESET_PATHS[0].read_text(encoding="utf-8"))
    rs = RulesetSchema.model_validate(rs_data)
    cit = SourceCitation(source_name="srd.md", source_kind="markdown", anchor="entry")

    act_entry = CompendiumEntry(
        entry_id="ent_action_1",
        category="action",
        title="Arcane Burst",
        body="category: power\nrequires_target: true\ntags: evade, arcane",
        structured_fields={},
        citation=cit,
        content_hash=canonical_sha256("act_1"),
    )
    cond_entry = CompendiumEntry(
        entry_id="ent_cond_1",
        category="condition",
        title="Dazed",
        body="blocks_tags: reaction\ndefault_duration_turns: 2",
        structured_fields={},
        citation=cit,
        content_hash=canonical_sha256("cond_1"),
    )
    form_entry = CompendiumEntry(
        entry_id="ent_form_1",
        category="form",
        title="Iron Golem Form",
        body="property_mode: delta_overlay\nproperty_deltas: str_score=4",
        structured_fields={},
        citation=cit,
        content_hash=canonical_sha256("form_1"),
    )
    creature_entry = CompendiumEntry(
        entry_id="ent_npc_1",
        category="creature",
        title="Ashfall Sentinel",
        body="properties: str_score=14\npools: vitality=18\ngranted_actions: lunge",
        structured_fields={},
        citation=cit,
        content_hash=canonical_sha256("npc_1"),
    )

    compiler = JitBlockCompiler()
    first = compiler.compile_entry(act_entry, ruleset=rs)
    assert first.from_cache is False
    assert first.block_kind == "action"
    assert ActionBlock.model_validate(first.compiled_payload).requires_target is True

    second = compiler.compile_entry(act_entry, ruleset=rs)
    assert second.from_cache is True
    assert second.compiled_payload == first.compiled_payload

    batch = compiler.batch_compile([creature_entry, cond_entry, form_entry], ruleset=rs)
    assert len(batch) == 3
    by_kind = {item.block_kind: item for item in batch}
    cond_model = ConditionBlock.model_validate(by_kind["condition"].compiled_payload)
    assert cond_model.default_duration_turns == 2
    assert (
        FormBlock.model_validate(by_kind["form"].compiled_payload).property_mode == "delta_overlay"
    )
    entity_model = EntityState.model_validate(by_kind["entity"].compiled_payload)
    assert entity_model.base_properties["str_score"] == 14
    assert compiler.cache_size() == 4
    compiler.clear_cache()
    assert compiler.cache_size() == 0
