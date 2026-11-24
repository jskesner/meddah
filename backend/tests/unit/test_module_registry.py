"""Unit tests for §1.0 Module Registry, Dormancy, RBAC, Sandbox, and Replay Round-Trip."""

from __future__ import annotations

import pytest

from app.ruleset_vm import (
    MINIMAL_PROFILE,
    ActionBlock,
    EntityState,
    MeddahModuleManifest,
    ModuleOverrideEvent,
    ModuleProvides,
    ModuleRegistry,
    PackageManifest,
    PropertyBlock,
    RulesetSchema,
    apply_event,
    execute_action,
    initialize_scene_state,
    replay_events,
    state_hash,
)
from app.ruleset_vm.blocks import EffectSpec
from app.ruleset_vm.vm import VmEvent


def _build_registry() -> ModuleRegistry:
    reg = ModuleRegistry()
    reg.register(
        MeddahModuleManifest(
            module_id="safety_accessibility",
            spec_section="1.10",
            label="Safety & Accessibility",
            provides=ModuleProvides(commands=("xcard",), ui_panels=("SafetyDrawer",)),
        )
    )
    reg.register(
        MeddahModuleManifest(
            module_id="gm_director",
            spec_section="1.3",
            label="GM Director",
            requires_primitives=("resolution_mechanic",),
            provides=ModuleProvides(commands=("oracle",), ui_panels=("OracleDrawer",)),
        )
    )
    reg.register(
        MeddahModuleManifest(
            module_id="tactical_vtt",
            spec_section="1.9",
            label="2.5D Tactical VTT",
            requires_primitives=("spatial_grid",),
            provides=ModuleProvides(commands=("measure",), ui_panels=("VttCanvas",)),
        )
    )
    reg.register(
        MeddahModuleManifest(
            module_id="warfare",
            spec_section="1.9.8",
            label="Mass Warfare",
            requires_primitives=("spatial_grid", "mass_units"),
            requires_modules=("tactical_vtt",),
            provides=ModuleProvides(commands=("muster",), ui_panels=("WarfarePanel",)),
        )
    )
    reg.register(
        MeddahModuleManifest(
            module_id="ui_effects",
            spec_section="1.7.5",
            label="Local UI Visual FX",
            scope="player_local",
            provides=ModuleProvides(ui_panels=("VfxSettings",)),
        )
    )
    return reg


@pytest.mark.zero_ai
def test_dormancy_and_dependency_gating() -> None:
    """Modules without required primitives resolve dormant and expose zero provides."""
    reg = _build_registry()
    reg.apply_profile(MINIMAL_PROFILE)

    # Ruleset declares zero optional primitives -> gm_director, tactical_vtt, warfare are dormant
    snaps_empty = reg.resolve_all(())
    assert snaps_empty["safety_accessibility"].state == "active"
    assert snaps_empty["gm_director"].state == "dormant"
    assert snaps_empty["tactical_vtt"].state == "dormant"
    assert snaps_empty["warfare"].state == "dormant"

    provides_empty = reg.active_provides(())
    assert provides_empty.commands == ("xcard",)
    assert "oracle" not in provides_empty.commands
    assert "measure" not in provides_empty.commands

    # Supplying spatial_grid + mass_units makes tactical_vtt & warfare available (not yet enabled)
    snaps_grid = reg.resolve_all(("spatial_grid", "mass_units"))
    assert snaps_grid["tactical_vtt"].state == "available"
    assert snaps_grid["warfare"].state == "available"
    assert reg.dependent_modules("tactical_vtt") == ("warfare",)

    # Enabling warfare without tactical_vtt keeps warfare unactivated until parent is active
    reg.set_enabled("warfare", True)
    assert reg.resolve_status("warfare", ("spatial_grid", "mass_units")).state == "available"
    reg.set_enabled("tactical_vtt", True)
    assert reg.resolve_status("warfare", ("spatial_grid", "mass_units")).state == "active"
    assert "muster" in reg.active_provides(("spatial_grid", "mass_units")).commands


@pytest.mark.zero_ai
def test_rbac_sandbox_clone_and_safe_boundary_overrides() -> None:
    """Guests can toggle only player_local; CoW sandbox never mutates live registry."""
    reg = _build_registry()

    assert reg.check_toggle_permission("ui_effects", seat_role="player", is_server_admin=False)
    assert not reg.check_toggle_permission(
        "tactical_vtt", seat_role="player", is_server_admin=False
    )
    assert not reg.check_toggle_permission(
        "tactical_vtt", seat_role="co_gm", is_server_admin=False, can_toggle_campaign_modules=False
    )
    assert reg.check_toggle_permission(
        "tactical_vtt", seat_role="co_gm", is_server_admin=False, can_toggle_campaign_modules=True
    )

    with pytest.raises(PermissionError):
        reg.queue_override(
            ModuleOverrideEvent(
                module_id="tactical_vtt",
                enabled=True,
                actor_seat_id="guest_1",
            ),
            seat_role="player",
            is_server_admin=False,
        )

    # Sandbox CoW clone experiments without touching live registry
    sandbox = reg.clone_sandbox()
    sandbox.set_enabled("tactical_vtt", True)
    assert sandbox.resolve_status("tactical_vtt", ("spatial_grid",)).state == "active"
    assert reg.resolve_status("tactical_vtt", ("spatial_grid",)).state == "available"

    # Safe boundary queue & flush
    reg.queue_override(
        ModuleOverrideEvent(
            module_id="tactical_vtt",
            enabled=True,
            boundary="next_scene_rest_or_session",
            actor_seat_id="host_1",
        ),
        seat_role="host",
        is_server_admin=True,
    )
    assert reg.resolve_status("tactical_vtt", ("spatial_grid",)).state == "available"
    applied = reg.flush_boundary("next_scene_rest_or_session")
    assert len(applied) == 1
    assert reg.resolve_status("tactical_vtt", ("spatial_grid",)).state == "active"


@pytest.mark.zero_ai
def test_module_toggle_round_trip_preserves_replay_state_hash() -> None:
    """enable -> play -> disable -> enable produces identical state hash across replay."""
    ruleset = RulesetSchema(
        manifest=PackageManifest(
            package_type="ruleset",
            package_id="mod_roundtrip",
            name="Module Roundtrip Test",
            version="0.1.0",
        ),
        properties={"resolve": PropertyBlock(prop_id="resolve", label="Resolve", default_value=3)},
        actions={
            "stride": ActionBlock(
                action_id="stride",
                label="Stride",
                default_effects=(
                    EffectSpec(
                        kind="advance_clock",
                        target_scope="scene",
                        target_key="progress",
                        formula="1",
                    ),
                ),
            )
        },
    )
    ent = EntityState(entity_id="pc_1", name="Tester")
    initial = initialize_scene_state(ruleset, "scene_rt", [ent], active_modules=("tactical_vtt",))

    res1 = execute_action(ruleset, initial, "pc_1", "stride")
    disable_evt = VmEvent(
        event_id="evt_mod_off",
        event_type="MODULE_OVERRIDE",
        actor_id="host",
        payload={"module_id": "tactical_vtt", "enabled": False},
    )
    s_disabled = apply_event(ruleset, res1.state, disable_evt)
    res2 = execute_action(ruleset, s_disabled, "pc_1", "stride")
    enable_evt = VmEvent(
        event_id="evt_mod_on",
        event_type="MODULE_OVERRIDE",
        actor_id="host",
        payload={"module_id": "tactical_vtt", "enabled": True},
    )
    s_reenabled = apply_event(ruleset, res2.state, enable_evt)

    all_events = [*res1.events, disable_evt, *res2.events, enable_evt]
    replayed = replay_events(ruleset, initial, all_events)
    assert state_hash(replayed) == state_hash(s_reenabled)
    assert replayed.active_modules == ("tactical_vtt",)
    assert replayed.clocks["progress"] == 2
