"""GPU/ROCm diagnostics (`meddah gpu-check`) and systemd unit generation (`meddah service`)."""

from __future__ import annotations

import grp
import os
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

from app.cli.models import GpuProbeReport


def _default_path_exists(path_str: str) -> bool:
    return Path(path_str).exists()


def _default_user_groups() -> tuple[str, ...]:
    names: list[str] = []
    try:
        for gid in os.getgroups():
            try:
                names.append(grp.getgrgid(gid).gr_name)
            except KeyError:
                continue
    except OSError:
        return ()
    return tuple(sorted(set(names)))


def _default_probe_nvidia() -> tuple[tuple[str, ...], float | None]:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return (), None
    proc = subprocess.run(
        [exe, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        return (), None
    names: list[str] = []
    max_vram_gb = 0.0
    for ln in proc.stdout.strip().splitlines():
        parts = [p.strip() for p in ln.split(",")]
        if parts and parts[0]:
            names.append(parts[0])
        if len(parts) >= 2:
            try:
                vram = round(float(parts[1]) / 1024.0, 2)
                if vram > max_vram_gb:
                    max_vram_gb = vram
            except ValueError:
                pass
    return tuple(names), (max_vram_gb if max_vram_gb > 0 else None)


def _default_probe_amd() -> tuple[tuple[str, ...], float | None, str | None]:
    rocminfo = shutil.which("rocminfo")
    if rocminfo:
        proc = subprocess.run(
            [rocminfo],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if proc.returncode == 0:
            names: list[str] = []
            gfx_hint: str | None = None
            for ln in proc.stdout.splitlines():
                stripped = ln.strip()
                if stripped.startswith("Marketing Name:") or stripped.startswith("Name:"):
                    val = stripped.split(":", 1)[1].strip()
                    if "gfx" in val.lower():
                        if "103" in val.lower():
                            gfx_hint = "10.3.0"
                        elif "110" in val.lower():
                            gfx_hint = "11.0.0"
                    elif val and not val.startswith("AMD Ryzen") and "CPU" not in val:
                        names.append(val)
            if names or gfx_hint:
                return tuple(dict.fromkeys(names)) or ("AMD ROCm GPU",), 8.0, gfx_hint

    # Fallback check on Linux sysfs PCI vendor 0x1002
    drm_root = Path("/sys/class/drm")
    if drm_root.is_dir():
        for vendor_file in sorted(drm_root.glob("card*/device/vendor")):
            try:
                if vendor_file.read_text(encoding="utf-8").strip().lower() == "0x1002":
                    return ("AMD Radeon GPU",), 8.0, "11.0.0"
            except OSError:
                continue
    return (), None, None


def _recommend_model(vram_gb: float | None, *, cpu_only: bool = False) -> str:
    if cpu_only or vram_gb is None or vram_gb < 6.0:
        return "qwen2.5:3b-instruct-q4_K_M"
    if vram_gb >= 12.0:
        return "qwen2.5:14b-instruct-q4_K_M"
    return "qwen2.5:7b-instruct-q4_K_M"


def run_gpu_check(
    *,
    setup_rocm: bool = False,
    probe_nvidia_fn: Callable[[], tuple[tuple[str, ...], float | None]] | None = None,
    probe_amd_fn: Callable[[], tuple[tuple[str, ...], float | None, str | None]] | None = None,
    path_exists_fn: Callable[[str], bool] | None = None,
    user_groups_fn: Callable[[], tuple[str, ...]] | None = None,
) -> GpuProbeReport:
    """Inspect NVIDIA/AMD/Vulkan hardware and recommend Docker profile & Ollama model."""
    nv_fn = probe_nvidia_fn or _default_probe_nvidia
    amd_fn = probe_amd_fn or _default_probe_amd
    exists_fn = path_exists_fn or _default_path_exists
    groups_fn = user_groups_fn or _default_user_groups

    kfd_ok = exists_fn("/dev/kfd")
    dri_ok = exists_fn("/dev/dri")
    groups = set(groups_fn())
    in_video = "video" in groups
    in_render = "render" in groups

    nv_names, nv_vram = nv_fn()
    if nv_names:
        return GpuProbeReport(
            vendor="nvidia",
            gpu_names=nv_names,
            vram_gb_estimate=nv_vram,
            rocm_kfd_present=kfd_ok,
            dri_present=dri_ok,
            user_in_video_group=in_video,
            user_in_render_group=in_render,
            recommended_compose_profile="ollama-nvidia",
            recommended_ollama_model=_recommend_model(nv_vram),
            setup_commands=(
                "docker compose -f docker/docker-compose.server.yml --profile ollama-nvidia up -d",
            ),
        )

    amd_names, amd_vram, gfx_override = amd_fn()
    if amd_names:
        warnings: list[str] = []
        cmds: list[str] = []
        if not kfd_ok:
            warnings.append("/dev/kfd missing; kernel AMDGPU/ROCm driver may not be loaded.")
            cmds.append("./tools/setup_gpu_host.sh")
        if not (in_video and in_render):
            warnings.append("Current user lacks 'video' and/or 'render' group membership.")
            cmds.append("sudo usermod -aG video,render $USER")
        if setup_rocm:
            cmds.append("./tools/setup_gpu_host.sh --check-rocm")
        if dri_ok and not kfd_ok:
            profile = "ollama-vulkan"
            cmds.append(
                "docker compose -f docker/docker-compose.server.yml --profile ollama-vulkan up -d"
            )
        else:
            profile = "ollama-amd"
            cmds.append(
                "docker compose -f docker/docker-compose.server.yml --profile ollama-amd up -d"
            )
        return GpuProbeReport(
            vendor="amd",
            gpu_names=amd_names,
            vram_gb_estimate=amd_vram,
            rocm_kfd_present=kfd_ok,
            dri_present=dri_ok,
            user_in_video_group=in_video,
            user_in_render_group=in_render,
            recommended_hsa_override=gfx_override,
            recommended_compose_profile=profile,
            recommended_ollama_model=_recommend_model(amd_vram),
            setup_commands=tuple(cmds),
            warnings=tuple(warnings),
        )

    if dri_ok and exists_fn("/dev/dri/renderD128"):
        return GpuProbeReport(
            vendor="intel",
            gpu_names=("Vulkan Render Device",),
            dri_present=True,
            user_in_video_group=in_video,
            user_in_render_group=in_render,
            recommended_compose_profile="ollama-vulkan",
            recommended_ollama_model=_recommend_model(None, cpu_only=True),
            setup_commands=(
                "docker compose -f docker/docker-compose.server.yml --profile ollama-vulkan up -d",
            ),
        )

    return GpuProbeReport(
        vendor="cpu_only",
        gpu_names=(),
        dri_present=dri_ok,
        user_in_video_group=in_video,
        user_in_render_group=in_render,
        recommended_compose_profile="ollama-cpu",
        recommended_ollama_model="qwen2.5:3b-instruct-q4_K_M",
        setup_commands=(
            "docker compose -f docker/docker-compose.server.yml up -d  # Zero-AI Tier A",
            "docker compose -f docker/docker-compose.server.yml "
            "--profile ollama-cpu up -d  # Tier B-Lite CPU",
        ),
        warnings=("No discrete GPU detected; defaulting to Tier-A Zero-AI or CPU Tier B-Lite.",),
    )


def render_systemd_unit(
    *,
    data_dir: Path,
    host: str = "0.0.0.0",
    port: int = 8420,
    user_mode: bool = True,
    exec_path: str = "meddah",
    ai_provider: str = "none",
) -> str:
    """Render a hardened systemd unit file for `meddah serve` with SIGTERM checkpointing."""
    wanted_by = "default.target" if user_mode else "multi-user.target"
    hardening_lines = (
        "" if user_mode else "NoNewPrivileges=true\nPrivateTmp=true\nProtectSystem=full\n"
    )
    resolved_data = Path(data_dir).resolve()
    return (
        "[Unit]\n"
        "Description=Meddah Universal Story Engine Headless Server\n"
        "After=network-online.target\n"
        "Wants=network-online.target\n\n"
        "[Service]\n"
        "Type=simple\n"
        f"Environment=MEDDAH_DATA_DIR={resolved_data}\n"
        f"Environment=AI_PROVIDER={ai_provider}\n"
        f"ExecStart={exec_path} serve --host {host} --port {port} --data-dir {resolved_data}\n"
        "Restart=on-failure\n"
        "RestartSec=5\n"
        "KillSignal=SIGTERM\n"
        "TimeoutStopSec=30\n"
        f"{hardening_lines}"
        "\n[Install]\n"
        f"WantedBy={wanted_by}\n"
    )


def install_systemd_service(
    *,
    data_dir: Path,
    output_path: Path | None = None,
    host: str = "0.0.0.0",
    port: int = 8420,
    user_mode: bool = True,
    exec_path: str = "meddah",
) -> Path:
    """Write a meddah.service systemd unit cleanly to output_path or standard user unit dir."""
    dest = (
        Path(output_path)
        if output_path is not None
        else (
            Path.home() / ".config" / "systemd" / "user" / "meddah.service"
            if user_mode
            else Path("/etc/systemd/system/meddah.service")
        )
    )
    dest.parent.mkdir(parents=True, exist_ok=True)
    unit_text = render_systemd_unit(
        data_dir=data_dir,
        host=host,
        port=port,
        user_mode=user_mode,
        exec_path=exec_path,
    )
    dest.write_text(unit_text, encoding="utf-8")
    return dest
