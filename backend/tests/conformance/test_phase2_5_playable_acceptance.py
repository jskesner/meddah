"""Phase 2.5 Conformance Gate: 30-min equivalent playable CLI slice across 3 showcase rulesets."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from app.cli import HeadlessLibraryStore, main

pytestmark = [pytest.mark.zero_ai, pytest.mark.conformance]

SHOWCASE_ACTION_SCRIPT_BY_RULESET: dict[str, tuple[str, ...]] = {
    "classic_d20_fantasy": (
        "look",
        "actions",
        "say Ready your steel beside the sinkhole.",
        "bow to comp_vane",
        "south",
        "east",
        "look",
        "use melee_strike npc_archivist_shade",
        "west",
        "north",
        "down",
        "use melee_strike npc_crypt_warden",
        "manual-roll on",
        "use melee_strike npc_crypt_warden",
        "sheet set pool vitality 12 Tabletop damage adjustment",
        "manual-roll cancel",
        "manual-roll off",
        "north",
        "timeskip propose 120 Catch breath beside the altar",
        "timeskip schedule Search altar reliefs",
        "timeskip vote approve",
        "sheet",
        "quit",
    ),
    "grimdark_d100_investigative": (
        "look",
        "actions",
        "whisper to comp_vane Check those lichen marks.",
        "south",
        "east",
        "use investigate_clue",
        "west",
        "north",
        "down",
        "east",
        "use push_investigation",
        "west",
        "use witness_horror",
        "sheet set pool sanity 50 GM sanity ruling",
        "wait 300",
        "time",
        "sheet",
        "quit",
    ),
    "narrative_2d6_clocks": (
        "look",
        "actions",
        "down",
        "use infiltrate_action npc_crypt_warden",
        "clocks",
        "north",
        "use resist_consequence",
        "south",
        "east",
        "use clear_stress_downtime",
        "sheet set prop prowl 3 Narrative boost",
        "timeskip gm 600 Downtime breather",
        "sheet",
        "quit",
    ),
}


@pytest.mark.parametrize("ruleset_id", sorted(SHOWCASE_ACTION_SCRIPT_BY_RULESET))
def test_phase2_5_playable_cli_slice_across_showcase_rulesets(
    ruleset_id: str,
    tmp_path: Path,
) -> None:
    """Attach CLI completes multi-floor exploration, combat/actions, overrides & time skips."""
    script_lines = SHOWCASE_ACTION_SCRIPT_BY_RULESET[ruleset_id]
    script_file = tmp_path / f"{ruleset_id}_script.txt"
    script_file.write_text("\n".join(script_lines) + "\n", encoding="utf-8")

    data_dir = tmp_path / f"data_{ruleset_id}"
    out = io.StringIO()
    err = io.StringIO()

    rc = main(
        [
            "--data-dir",
            str(data_dir),
            "attach",
            "--ruleset",
            ruleset_id,
            "--actor-name",
            "Lyra",
            "--script",
            str(script_file),
        ],
        stdout=out,
        stderr=err,
    )
    assert rc == 0, err.getvalue()
    transcript = out.getvalue()
    assert "Ashfall Courtyard [Z0]" in transcript
    assert "Floor transition: Z0 -> Z-1" in transcript
    assert f"[ruleset={ruleset_id}]" in transcript

    store = HeadlessLibraryStore(data_dir)
    camps = store.list_campaigns()
    assert len(camps) == 1
    st = store.start_session(camps[0].campaign_id)
    assert st.ruleset_id == ruleset_id
    assert store.active_engine is not None
    assert store.active_engine.verify_replay_hash() is True
