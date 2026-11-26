"""Unit tests for headless library store, secrets, daemon transports, systemd & Docker."""

from __future__ import annotations

import asyncio
import io
import json
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest
import yaml

from app.cli import (
    HeadlessLibraryStore,
    HeadlessRpcClient,
    MeddahHeadlessServer,
    WsMudClient,
    install_systemd_service,
    main,
    resolve_headless_secret,
    run_gpu_check,
)

pytestmark = pytest.mark.zero_ai

REPO_ROOT = Path(__file__).resolve().parents[3]


def _start_server_thread(
    server: MeddahHeadlessServer,
) -> tuple[asyncio.AbstractEventLoop, threading.Thread]:
    ready_evt = threading.Event()
    loop_holder: list[asyncio.AbstractEventLoop] = []

    def _runner() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop_holder.append(loop)
        loop.run_until_complete(server.start())
        ready_evt.set()
        try:
            loop.run_forever()
        finally:
            loop.close()

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
    assert ready_evt.wait(timeout=5.0)
    return loop_holder[0], thread


def _stop_server_thread(
    server: MeddahHeadlessServer,
    loop: asyncio.AbstractEventLoop,
    thread: threading.Thread,
) -> None:
    fut = asyncio.run_coroutine_threadsafe(server.shutdown(), loop)
    fut.result(timeout=5.0)
    loop.call_soon_threadsafe(loop.stop)
    thread.join(timeout=5.0)


def test_resolve_headless_secret_priority_order(tmp_path: Path) -> None:
    """Secret resolution follows *_FILE > env var > local config secret precedence."""
    secrets_dir = tmp_path / "run_secrets"
    config_dir = tmp_path / "cfg"
    secrets_dir.mkdir()
    config_dir.mkdir()

    cfg_secret = config_dir / "openai_api_key.secret"
    cfg_secret.write_text("from_config_file\n", encoding="utf-8")
    assert (
        resolve_headless_secret("OPENAI_API_KEY", config_dir=config_dir, env={})
        == "from_config_file"
    )

    assert (
        resolve_headless_secret(
            "OPENAI_API_KEY",
            config_dir=config_dir,
            env={"OPENAI_API_KEY": "from_env"},
        )
        == "from_env"
    )

    file_secret = tmp_path / "mounted.key"
    file_secret.write_text("from_file_override\n", encoding="utf-8")
    assert (
        resolve_headless_secret(
            "OPENAI_API_KEY",
            secrets_dir=secrets_dir,
            config_dir=config_dir,
            env={
                "OPENAI_API_KEY": "from_env",
                "OPENAI_API_KEY_FILE": str(file_secret),
            },
        )
        == "from_file_override"
    )


def test_headless_library_store_campaign_hotswap_seats_backups_and_cli(tmp_path: Path) -> None:
    """Store & CLI manage multiple campaigns, hot-swapping, exports, seats, and rulesets."""
    data_dir = tmp_path / "meddah_data"
    out = io.StringIO()

    assert (
        main(
            [
                "--data-dir",
                str(data_dir),
                "--json",
                "campaign",
                "create",
                "camp_d20",
                "--ruleset",
                "classic_d20_fantasy",
            ],
            stdout=out,
        )
        == 0
    )
    assert (
        main(
            [
                "--data-dir",
                str(data_dir),
                "--json",
                "campaign",
                "create",
                "camp_2d6",
                "--ruleset",
                "narrative_2d6_clocks",
            ],
            stdout=out,
        )
        == 0
    )

    store = HeadlessLibraryStore(data_dir)
    assert len(store.list_campaigns()) == 2
    assert len(store.list_rulesets()) >= 7

    val_res = store.validate_ruleset("classic_d20_fantasy")
    assert val_res["valid"] is True

    # Hot-swap sessions & verify auto-checkpoint persisted
    st1 = store.start_session("camp_d20")
    assert st1.active_campaign_id == "camp_d20"
    assert store.active_engine is not None
    store.active_engine.execute_command("d")
    st2 = store.switch_session("camp_2d6")
    assert st2.active_campaign_id == "camp_2d6"
    back_to_1 = store.switch_session("camp_d20")
    assert back_to_1.current_room_id == "sunken_vestibule"

    # Seat invites, approval, kick, revoke
    seat, raw_tok = store.invite_seat(role="player", label="Alice")
    assert store.authenticate_seat_token(raw_tok) is None
    approved = store.approve_seat(seat.seat_id)
    assert approved.status == "approved"
    assert store.authenticate_seat_token(raw_tok) is not None
    store.kick_seat(seat.seat_id)
    assert store.authenticate_seat_token(raw_tok) is None
    store.revoke_token(raw_tok)

    # Export + Backup + Import campaign archive
    archive_path = tmp_path / "camp_d20.rpgcampaign"
    store.export_campaign("camp_d20", archive_path)
    assert archive_path.is_file()
    imported = store.import_campaign(archive_path, override_campaign_id="camp_d20_clone")
    assert imported.campaign_id == "camp_d20_clone"
    backup_file = store.backup_session("camp_d20")
    assert backup_file.is_file()


def test_headless_server_unix_http_ws_and_graceful_shutdown(
    tmp_path: Path,
    allow_loopback_port: Callable[[int], None],
) -> None:
    """Server serves health/ready, zero-token UDS, Bearer TCP RPC, WS MUD, & shutdown cp."""
    data_dir = tmp_path / "srv_data"
    sock_path = Path(f"/tmp/meddah_test_{int(time.monotonic() * 1000)}.sock")
    store = HeadlessLibraryStore(data_dir)
    admin_tok = store.ensure_admin_token()
    store.create_campaign("ashfall", "Ashfall Live", "narrative_2d6_clocks")
    store.start_session("ashfall")
    seat, seat_tok = store.invite_seat(role="player", label="Scout", auto_approve=True)
    _ = seat

    server = MeddahHeadlessServer(
        store,
        host="127.0.0.1",
        port=0,
        admin_sock=sock_path,
        serve_web_client=True,
    )
    loop, thread = _start_server_thread(server)
    allow_loopback_port(server.bound_port)
    base_url = f"http://127.0.0.1:{server.bound_port}"

    try:
        # Health & Readiness probes
        with urllib.request.urlopen(f"{base_url}/api/health", timeout=3.0) as resp:
            health = json.loads(resp.read().decode("utf-8"))
        assert health["status"] == "ok"

        with urllib.request.urlopen(f"{base_url}/api/ready", timeout=3.0) as resp:
            ready = json.loads(resp.read().decode("utf-8"))
        assert ready["ready"] is True
        assert ready["active_campaign_id"] == "ashfall"

        # Unauthorized TCP RPC fails with 401
        bad_req = urllib.request.Request(
            f"{base_url}/api/rpc",
            data=b'{"method":"session.status"}',
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(bad_req, timeout=3.0)
        assert exc_info.value.code == 401

        # Zero-token local UNIX Domain Socket admin RPC succeeds
        uds_client = HeadlessRpcClient(admin_sock=sock_path)
        campaigns = cast(list[dict[str, object]], uds_client.call("campaign.list"))
        assert campaigns[0]["campaign_id"] == "ashfall"

        # Remote TCP RPC with admin Bearer token
        tcp_client = HeadlessRpcClient(server_url=base_url, token=admin_tok)
        st = cast(dict[str, object], tcp_client.call("session.status"))
        assert st["active_campaign_id"] == "ashfall"

        # Real RFC 6455 WebSocket interactive MUD via Seat Bearer token
        ws = WsMudClient(base_url, token=seat_tok)
        ws.connect()
        try:
            turn1 = ws.send_command("look")
            assert turn1.current_room_id == "ashfall_courtyard"
            turn2 = ws.send_command("d")
            assert turn2.current_room_id == "sunken_vestibule"
            assert any("Z0 -> Z-1" in ln for ln in turn2.output_lines)
        finally:
            ws.close()
    finally:
        _stop_server_thread(server, loop, thread)

    assert server.shutdown_checkpoint_written is True
    assert not sock_path.exists()
    # Verify shutdown checkpoint persisted cleanly on disk
    reloaded = HeadlessLibraryStore(data_dir)
    info = reloaded.get_campaign_info("ashfall")
    assert int(cast(int, info["checkpoint_count"])) >= 2


def test_gpu_check_systemd_and_docker_compose_profiles(tmp_path: Path) -> None:
    """gpu-check detects NVIDIA/AMD/Vulkan/CPU; systemd and Docker assets validate."""
    nvidia = run_gpu_check(
        probe_nvidia_fn=lambda: (("NVIDIA RTX 4080",), 16.0),
        probe_amd_fn=lambda: ((), None, None),
        path_exists_fn=lambda _: False,
        user_groups_fn=lambda: ("video",),
    )
    assert nvidia.vendor == "nvidia"
    assert nvidia.recommended_compose_profile == "ollama-nvidia"
    assert nvidia.recommended_ollama_model == "qwen2.5:14b-instruct-q4_K_M"

    amd = run_gpu_check(
        setup_rocm=True,
        probe_nvidia_fn=lambda: ((), None),
        probe_amd_fn=lambda: (("Radeon RX 7800 XT",), 16.0, "11.0.0"),
        path_exists_fn=lambda p: p in {"/dev/kfd", "/dev/dri"},
        user_groups_fn=lambda: ("users",),
    )
    assert amd.vendor == "amd"
    assert amd.recommended_compose_profile == "ollama-amd"
    assert amd.recommended_hsa_override == "11.0.0"
    assert any("usermod" in cmd for cmd in amd.setup_commands)

    cpu = run_gpu_check(
        probe_nvidia_fn=lambda: ((), None),
        probe_amd_fn=lambda: ((), None, None),
        path_exists_fn=lambda _: False,
        user_groups_fn=lambda: (),
    )
    assert cpu.vendor == "cpu_only"
    assert cpu.recommended_compose_profile == "ollama-cpu"

    unit_path = install_systemd_service(
        data_dir=tmp_path / "data",
        output_path=tmp_path / "meddah.service",
        user_mode=False,
    )
    unit_text = unit_path.read_text(encoding="utf-8")
    assert "KillSignal=SIGTERM" in unit_text
    assert "NoNewPrivileges=true" in unit_text

    # CLI gpu-check entrypoint smoke
    cli_out = io.StringIO()
    assert main(["--json", "gpu-check"], stdout=cli_out) == 0
    assert "recommended_compose_profile" in cli_out.getvalue()

    # Validate Docker Compose YAML & Dockerfile structural contracts
    compose_path = REPO_ROOT / "docker" / "docker-compose.server.yml"
    dockerfile_path = REPO_ROOT / "docker" / "Dockerfile.server"
    assert compose_path.is_file()
    assert dockerfile_path.is_file()

    compose = cast(dict[str, object], yaml.safe_load(compose_path.read_text(encoding="utf-8")))
    services = cast(dict[str, dict[str, object]], compose["services"])
    expected_profiles = {
        "ollama-nvidia",
        "ollama-amd",
        "ollama-vulkan",
        "ollama-cpu",
        "piper-tts",
        "tunnel",
    }
    found_profiles: set[str] = set()
    for svc in services.values():
        profs = cast(list[str], svc.get("profiles", []))
        found_profiles.update(profs)
    assert expected_profiles.issubset(found_profiles)
    assert "STOPSIGNAL SIGTERM" in dockerfile_path.read_text(encoding="utf-8")
