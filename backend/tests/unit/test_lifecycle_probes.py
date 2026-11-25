"""Unit tests for the 14-domain Semantic & Lifecycle Discovery Probes and Tier-B checkpoints."""

from __future__ import annotations

import io
import json
import urllib.request
from typing import cast

import pytest

from app.ingestion import (
    DOMAIN_BY_ID,
    FOURTEEN_PROBE_DOMAINS,
    CompendiumIndex,
    OllamaMicroProbeClient,
    ProbeCheckpointState,
    ProbeDomainResult,
    TierBMicroProbeRequest,
    parse_markdown,
    run_deterministic_probes,
    run_ruleset_schema_probes,
    run_tier_b_micro_probes,
)
from app.ruleset_vm import PackageManifest, RulesetSchema

pytestmark = pytest.mark.zero_ai


def test_fourteen_probe_domains_complete_and_ordered() -> None:
    """All 14 universal discovery probes must be uniquely numbered 1..14."""
    assert len(FOURTEEN_PROBE_DOMAINS) == 14
    assert [spec.probe_number for spec in FOURTEEN_PROBE_DOMAINS] == list(range(1, 15))
    assert set(DOMAIN_BY_ID) == {spec.domain_id for spec in FOURTEEN_PROBE_DOMAINS}


def test_strict_null_absent_guarantee_on_non_mechanical_text() -> None:
    """Probes must report absent/none and emit zero proposals when mechanics are absent."""
    doc = parse_markdown(
        "# Quiet Almanac\n\nA tranquil coastal town awaits passing ships.",
        source_name="almanac.md",
    )
    results = run_deterministic_probes(doc)
    assert len(results) == 14
    for res in results:
        assert res.status == "absent"
        assert res.declared_value == "none"
        assert res.confidence_score == 0.0
        assert res.extracted_primitives == ()
        assert res.proposals == ()


def test_ruleset_schema_probes_report_absent_for_bare_ruleset() -> None:
    """Auditing an empty RulesetSchema leaves optional subsystems cleanly dormant."""
    bare = RulesetSchema(
        manifest=PackageManifest(
            package_type="ruleset",
            package_id="bare_test",
            name="Bare Test",
            version="0.1.0",
        )
    )
    results = run_ruleset_schema_probes(bare)
    assert len(results) == 14
    assert all(res.status == "absent" and res.declared_value == "none" for res in results)


def test_probes_extract_forms_stealth_theft_disguise_and_vitality() -> None:
    """Probes detect explicit vitality topology, FormBlock, and 3-pillar covert bindings."""
    md = """# Shadow Guild Rules

## Vitality & Hit Locations
Combat tracks both total vitality and hit location damage (composite_dual).

## Dying Condition
Characters at zero vitality gain the dying condition until triage is applied.

## Wolf Form Transformation
A mystic can shapeshift into a wolf form with heightened speed.

## Stealth and Pickpocket Rules
Using stealth keeps an agent hidden in dim light; pickpocket lets thieves steal pouches.

## Disguise & False Alias
Tailors craft forged identity disguises allowing agents to impersonate guards.
"""
    doc = parse_markdown(md, source_name="shadow_guild.md")
    idx = CompendiumIndex(":memory:")
    try:
        idx.index_parsed_document(doc)
        results = run_deterministic_probes(doc, compendium_index=idx)
    finally:
        idx.close()

    by_id = {r.domain_id: r for r in results}
    assert by_id["vitality_and_death"].status == "found"
    assert by_id["vitality_and_death"].declared_value == "composite_dual"
    assert any(p.block_category == "condition" for p in by_id["vitality_and_death"].proposals)

    cap = by_id["capabilities_forms_covert"]
    assert cap.status == "found"
    assert "forms" in cap.extracted_primitives
    assert "covert_stealth" in cap.extracted_primitives
    assert "covert_theft" in cap.extracted_primitives
    assert any(p.block_category == "form" for p in cap.proposals)

    covert_props = [p for p in cap.proposals if p.block_category == "covert_ops"]
    assert len(covert_props) == 1
    payload = covert_props[0].proposed_payload
    assert payload["stealth"] is not None
    assert payload["theft"] is not None
    assert payload["disguise"] is not None

    # Disguise-only document emits covert_ops with only disguise enabled
    disguise_doc = parse_markdown(
        "# Court Intrigue\n\n## Disguise Protocols\nAgents may adopt an alias and disguise.\n",
        source_name="court.md",
    )
    disguise_res = {r.domain_id: r for r in run_deterministic_probes(disguise_doc)}
    social = disguise_res["social_morale_disguise"]
    assert social.status == "found"
    assert "covert_disguise" in social.extracted_primitives
    d_props = [p for p in social.proposals if p.block_category == "covert_ops"]
    assert len(d_props) == 1
    assert d_props[0].proposed_payload["disguise"] is not None
    assert d_props[0].proposed_payload["stealth"] is None
    assert d_props[0].proposed_payload["theft"] is None


def test_tier_b_micro_probes_token_budget_checkpoint_resume_and_fallback() -> None:
    """Tier-B probes stay within <=8192 tokens, pause/resume cleanly, and handle invalid JSON."""
    big_body = "Vitality wound bleeding healing stealth disguise starship " * 900
    doc = parse_markdown(f"# Mammoth Rulebook\n\n## Core\n{big_body}\n", source_name="big.md")
    seen_tokens: list[int] = []

    def _fake_llm(req: TierBMicroProbeRequest) -> dict[str, object]:
        seen_tokens.append(req.estimated_tokens)
        if req.domain_id == "vitality_and_death":
            return {
                "probe_number": req.probe_number,
                "domain_id": req.domain_id,
                "label": req.label,
                "status": "found",
                "declared_value": "monolithic",
                "confidence_score": 0.9,
                "summary": "Extracted by fake Tier-B model.",
            }
        if req.domain_id == "world_cosmology":
            # Invalid confidence triggers deterministic fallback cleanly
            return {"status": "found", "confidence_score": 99.0}
        return {
            "probe_number": req.probe_number,
            "domain_id": req.domain_id,
            "label": req.label,
            "status": "absent",
            "declared_value": "none",
            "confidence_score": 0.0,
            "summary": "Absent.",
        }

    full_results, full_cp = run_tier_b_micro_probes(doc, micro_probe_fn=_fake_llm)
    assert len(full_results) == 14
    assert full_cp.pending_domain_ids == ()
    assert all(tok <= 8192 for tok in seen_tokens)
    by_id = {r.domain_id: r for r in full_results}
    assert by_id["vitality_and_death"].declared_value == "monolithic"
    assert isinstance(by_id["world_cosmology"], ProbeDomainResult)

    # Pause after 7 probes, serialize checkpoint to JSON, and resume
    part1, cp1 = run_tier_b_micro_probes(doc, micro_probe_fn=_fake_llm, max_domains_per_call=7)
    assert len(part1) == 7
    assert len(cp1.completed_domains) == 7
    assert len(cp1.pending_domain_ids) == 7

    reloaded_cp = ProbeCheckpointState.model_validate_json(cp1.model_dump_json())
    resumed, cp2 = run_tier_b_micro_probes(
        doc,
        micro_probe_fn=_fake_llm,
        checkpoint=reloaded_cp,
    )
    assert cp2.pending_domain_ids == ()
    assert [r.model_dump(mode="json") for r in full_results] == [
        r.model_dump(mode="json") for r in resumed
    ]


def test_ollama_micro_probe_client_request_payload_mocked(monkeypatch: pytest.MonkeyPatch) -> None:
    """OllamaMicroProbeClient posts temperature=0 + format schema without network traffic."""
    captured: dict[str, object] = {}

    class _FakeResp:
        def __init__(self, body_bytes: bytes) -> None:
            self._buf = io.BytesIO(body_bytes)

        def read(self) -> bytes:
            return self._buf.read()

        def __enter__(self) -> _FakeResp:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    def _fake_urlopen(req: urllib.request.Request, timeout: float = 0.0) -> _FakeResp:
        captured["url"] = req.full_url
        captured["timeout"] = timeout
        assert isinstance(req.data, bytes)
        captured["payload"] = json.loads(req.data.decode("utf-8"))
        inner = json.dumps(
            {
                "probe_number": 1,
                "domain_id": "vitality_and_death",
                "label": "Vitality",
                "status": "absent",
                "declared_value": "none",
                "confidence_score": 0.0,
            }
        )
        return _FakeResp(json.dumps({"response": inner}).encode("utf-8"))

    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)

    client = OllamaMicroProbeClient(base_url="http://127.0.0.1:11434/", model="qwen2.5:7b")
    req = TierBMicroProbeRequest(
        probe_number=1,
        domain_id="vitality_and_death",
        label="Vitality",
        prompt_text="Extract vitality.",
        estimated_tokens=10,
        response_json_schema={"type": "object"},
    )
    out = client(req)
    assert out["status"] == "absent"
    assert captured["url"] == "http://127.0.0.1:11434/api/generate"
    sent = cast(dict[str, object], captured["payload"])
    assert sent["model"] == "qwen2.5:7b"
    assert sent["stream"] is False
    assert sent["format"] == {"type": "object"}
    assert sent["options"] == {"temperature": 0}
