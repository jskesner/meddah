"""Hypothesis property tests for the Phase 2.5 CLI MUD Engine replay & safety invariants."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.cli import CampaignMetadata, MudSessionEngine
from app.ingestion import SystemWizardConfig, run_deterministic_system_wizard

pytestmark = pytest.mark.zero_ai

_RULESET, _ = run_deterministic_system_wizard(
    SystemWizardConfig(
        package_id="prop_cli_mud",
        name="Property CLI MUD",
        paradigm="tiered_2d6",
        enable_forms=True,
        covert_pillars=("stealth", "theft", "disguise"),
    )
)

VALID_CMD_SEQ = st.lists(
    st.sampled_from(
        [
            "look",
            "d",
            "u",
            "n",
            "s",
            "e",
            "w",
            "sheet",
            "sheet set prop might 5 prop_tune",
            "sheet set pool vitality 15 pool_tune",
            "wait 30",
            "form shift feral_aspect",
            "form revert",
            "hide npc_bone_sentinel",
            "roll 2d6",
        ]
    ),
    min_size=1,
    max_size=12,
)


@given(cmd=st.text(max_size=100))
@settings(max_examples=30)
def test_arbitrary_mud_input_never_raises_unhandled_exception(cmd: str) -> None:
    """Property: arbitrary text submitted to execute_command never crashes the CLI loop."""
    meta = CampaignMetadata(
        campaign_id="prop_fuzz",
        name="Prop Fuzz",
        ruleset_id=_RULESET.manifest.package_id,
        ruleset_hash=_RULESET.content_hash(),
        scene_seed="prop_seed",
    )
    engine = MudSessionEngine(meta, _RULESET)
    res = engine.execute_command(cmd)
    assert res.event_seq == engine.state.event_seq


@given(cmds=VALID_CMD_SEQ)
@settings(max_examples=25)
def test_command_sequences_preserve_deterministic_replay_hash(cmds: list[str]) -> None:
    """Property: arbitrary sequences of CLI VM commands maintain exact replay_events parity."""
    meta = CampaignMetadata(
        campaign_id="prop_seq",
        name="Prop Seq",
        ruleset_id=_RULESET.manifest.package_id,
        ruleset_hash=_RULESET.content_hash(),
        scene_seed="prop_seq_seed",
    )
    engine = MudSessionEngine(meta, _RULESET)
    for cmd in cmds:
        engine.execute_command(cmd)
    assert engine.verify_replay_hash() is True
