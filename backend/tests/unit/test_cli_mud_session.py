"""Unit tests for the Phase 2.5 Deterministic Terminal MUD Session Engine."""

from __future__ import annotations

import pytest

from app.cli import (
    CampaignMetadata,
    MudSessionEngine,
)
from app.ingestion import SystemWizardConfig, run_deterministic_system_wizard

pytestmark = pytest.mark.zero_ai


def _make_covert_and_forms_engine() -> MudSessionEngine:
    ruleset, _ = run_deterministic_system_wizard(
        SystemWizardConfig(
            package_id="ashfall_test_rules",
            name="Ashfall Test Rules",
            paradigm="tiered_2d6",
            enable_forms=True,
            covert_pillars=("stealth", "theft", "disguise"),
        )
    )
    meta = CampaignMetadata(
        campaign_id="camp_test",
        name="Test Campaign",
        ruleset_id=ruleset.manifest.package_id,
        ruleset_hash=ruleset.content_hash(),
        scene_seed="test_seed_1",
    )
    return MudSessionEngine(meta, ruleset)


def test_mud_navigation_multi_floor_sheet_override_and_manual_roll() -> None:
    """MUD handles Z0<->Z-1 navigation, direct SHEET_OVERRIDE, and manual-roll toggle."""
    engine = _make_covert_and_forms_engine()

    # Initial Courtyard Z0 -> Down to Sunken Vestibule Z-1 -> North to Ossuary Nave
    look_res = engine.execute_command("look")
    assert any("Ashfall Courtyard [Z0]" in ln for ln in look_res.output_lines)

    down_res = engine.execute_command("d")
    assert down_res.current_room_id == "sunken_vestibule"
    assert any("Z0 -> Z-1" in ln for ln in down_res.output_lines)

    north_res = engine.execute_command("north")
    assert north_res.current_room_id == "ossuary_nave"

    # Direct SHEET_OVERRIDE property, pool, condition & tag edits
    prop_res = engine.execute_command("sheet set prop might 6 Heroic surge")
    assert prop_res.error is None
    assert engine.state.entities["pc_lead"].base_properties["might"] == 6

    pool_res = engine.execute_command("sheet set pool vitality 14 Table adjust")
    assert pool_res.error is None
    assert engine.state.entities["pc_lead"].pools["vitality"] == 14

    cond_res = engine.execute_command("sheet cond add off_balance 2")
    assert "off_balance" in engine.state.entities["pc_lead"].conditions
    assert cond_res.error is None

    engine.execute_command("sheet cond remove off_balance")
    assert "off_balance" not in engine.state.entities["pc_lead"].conditions

    engine.execute_command("sheet tag add blessed_banner")
    assert "blessed_banner" in engine.state.entities["pc_lead"].tags

    # Manual-roll mode pauses strike with formula prompt, then resolve/off completes it
    on_res = engine.execute_command("manual-roll on")
    assert engine.manual_roll_mode is True
    assert on_res.error is None

    paused = engine.execute_command("use strike npc_bone_sentinel")
    assert paused.pending_manual_roll is not None
    assert paused.pending_manual_roll["action_id"] == "strike"

    resolved = engine.execute_command("manual-roll resolve")
    assert resolved.pending_manual_roll is None
    assert any("Roll:" in ln for ln in resolved.output_lines)

    engine.execute_command("manual-roll off")
    assert engine.manual_roll_mode is False
    assert engine.verify_replay_hash() is True


def test_mud_forms_covert_disguise_slots_and_time_skip_voting() -> None:
    """MUD executes form shift/revert, stealth, theft, disguise presets & time-skip voting."""
    engine = _make_covert_and_forms_engine()

    # Alternate Forms
    flist = engine.execute_command("form list")
    assert any("feral_aspect" in ln for ln in flist.output_lines)
    fshift = engine.execute_command("form shift feral_aspect")
    assert fshift.error is None
    assert engine.state.entities["pc_lead"].active_form is not None
    assert engine.state.entities["pc_lead"].active_form.form_id == "feral_aspect"
    frevert = engine.execute_command("form revert")
    assert frevert.error is None
    assert engine.state.entities["pc_lead"].active_form is None

    # Move down to Crypt Warden (Z-1) for Stealth & Theft
    engine.execute_command("d")
    hide_res = engine.execute_command("hide npc_crypt_warden")
    assert hide_res.error is None
    assert engine.state.awareness_map["npc_crypt_warden"]["pc_lead"] == "unaware"

    steal_res = engine.execute_command("steal crypt_vault_key from npc_crypt_warden")
    assert steal_res.error is None
    inv_res = engine.execute_command("inv")
    assert any("crypt_vault_key" in ln for ln in inv_res.output_lines)
    assert any("stolen" in ln for ln in inv_res.output_lines)

    # Disguise preset save + timed don via synchronized TimeSkipProposal + vote
    save_res = engine.execute_command(
        "disguise save dock_clerk alias_clerk Archivist Clerk --duration 60"
    )
    assert save_res.error is None
    don_res = engine.execute_command("disguise don dock_clerk")
    assert don_res.pending_time_skip is not None
    assert engine.state.elapsed_world_seconds == 0

    sched_res = engine.execute_command("timeskip schedule sharpen blades")
    assert sched_res.error is None

    vote_res = engine.execute_command("timeskip vote approve")
    assert vote_res.error is None
    assert engine.state.elapsed_world_seconds == 60
    assert engine.state.entities["pc_lead"].active_disguise is not None
    assert engine.state.entities["pc_lead"].active_disguise.presented_name == "Archivist Clerk"

    # GM direct time skip + wait + rewind checkpoint parity
    cp = engine.create_checkpoint("before_gm_skip")
    gm_skip = engine.execute_command("timeskip gm 120 Torch burn")
    assert gm_skip.error is None
    assert engine.state.elapsed_world_seconds == 180

    rewound = engine.rewind_to_event(cp.event_seq)
    assert rewound.state_hash == cp.state_hash
    assert engine.state.elapsed_world_seconds == 60
    assert engine.verify_replay_hash() is True


def test_mud_dormant_covert_ops_emotes_dice_and_snapshot_roundtrip() -> None:
    """Covert commands degrade gracefully when dormant; emotes & snapshots replay cleanly."""
    ruleset, _ = run_deterministic_system_wizard(
        SystemWizardConfig(
            package_id="dormant_covert",
            name="Dormant Covert",
            paradigm="tiered_2d6",
            covert_pillars=(),
        )
    )
    meta = CampaignMetadata(
        campaign_id="dormant_camp",
        name="Dormant",
        ruleset_id=ruleset.manifest.package_id,
        ruleset_hash=ruleset.content_hash(),
        scene_seed="dormant_seed",
    )
    engine = MudSessionEngine(meta, ruleset)

    hide_res = engine.execute_command("hide")
    assert hide_res.error is None
    assert any("dormant" in ln.lower() for ln in hide_res.output_lines)

    roll_res = engine.execute_command("roll 2d6")
    assert any("Rolled:" in ln for ln in roll_res.output_lines)

    shout_res = engine.execute_command("shout Ready at the gate!")
    assert any("shouts" in ln for ln in shout_res.output_lines)

    pose_res = engine.execute_command('act (calmly) adjusts lantern, "Into the dark."')
    assert any("Traveler" in ln for ln in pose_res.output_lines)

    snap = engine.to_snapshot_dict()
    restored = MudSessionEngine.from_snapshot_dict(snap, ruleset)
    assert restored.verify_replay_hash() is True
    assert (
        restored.execute_command("status").state_hash == engine.execute_command("status").state_hash
    )
