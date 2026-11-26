"""Pydantic schemas and headless secret resolution for the Phase 2.5 CLI & Server."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ServerMode = Literal["table", "guild-server"]
AiProviderChoice = Literal["none", "ollama", "openai", "anthropic", "gemini"]
HeadlessSeatRole = Literal["host", "gm", "co_gm", "host_player", "player", "spectator"]
SeatStatus = Literal["pending", "approved", "kicked", "revoked"]


class RoomNodeSpec(BaseModel):
    """Lightweight starter exploration room connecting multi-floor Z0 <-> Z-1 navigation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    room_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    floor_index: int = 0
    exits: dict[str, str] = Field(default_factory=dict)
    npc_ids: tuple[str, ...] = ()
    prop_notes: tuple[str, ...] = ()


class CampaignMetadata(BaseModel):
    """Persistent campaign descriptor stored inside the headless multi-campaign library."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    campaign_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    ruleset_id: str = Field(min_length=1)
    ruleset_hash: str = Field(min_length=1)
    ruleset_path: str = ""
    scene_seed: str = Field(min_length=1)
    description: str = ""
    created_order: int = 0


class SeatRecord(BaseModel):
    """Registered player, GM, host, or spectator seat with hashed bearer credential."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    seat_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    role: HeadlessSeatRole = "player"
    status: SeatStatus = "pending"
    token_hash: str = Field(min_length=1)
    entity_id: str | None = None


class CheckpointSummary(BaseModel):
    """Saved deterministic checkpoint metadata enabling rewind and atomic backup."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    checkpoint_id: str = Field(min_length=1)
    campaign_id: str = Field(min_length=1)
    event_seq: int = Field(ge=0)
    state_hash: str = Field(min_length=1)
    label: str = Field(min_length=1)


class SessionStatusSnapshot(BaseModel):
    """Live runtime status summary for the hot-swappable active campaign session."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    active_campaign_id: str | None = None
    active_campaign_name: str | None = None
    ruleset_id: str | None = None
    ruleset_hash: str | None = None
    running: bool = False
    event_seq: int = 0
    elapsed_world_seconds: int = 0
    current_room_id: str | None = None
    manual_roll_mode: bool = False
    ai_provider: AiProviderChoice = "none"
    server_mode: ServerMode = "table"
    connected_seats: int = 0
    active_entities: tuple[str, ...] = ()


class MudTurnResult(BaseModel):
    """Structured result emitted for every Terminal CLI MUD or WebSocket turn."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    command_raw: str
    category: str
    output_lines: tuple[str, ...]
    state_hash: str
    event_seq: int = Field(ge=0)
    elapsed_world_seconds: int = Field(ge=0)
    current_room_id: str = Field(min_length=1)
    pending_manual_roll: dict[str, object] | None = None
    pending_time_skip: dict[str, object] | None = None
    error: str | None = None


class GpuProbeReport(BaseModel):
    """Hardware & container runtime probe report produced by `meddah gpu-check`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    vendor: Literal["nvidia", "amd", "intel", "cpu_only"]
    gpu_names: tuple[str, ...] = ()
    vram_gb_estimate: float | None = None
    rocm_kfd_present: bool = False
    dri_present: bool = False
    user_in_video_group: bool = False
    user_in_render_group: bool = False
    recommended_hsa_override: str | None = None
    recommended_compose_profile: str
    recommended_ollama_model: str
    setup_commands: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


def resolve_headless_secret(
    env_var: str,
    *,
    secrets_dir: Path | None = None,
    config_dir: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> str | None:
    """Resolve a server secret cleanly without touching campaign files or SQLite logs.

    Priority order:
    1. Docker Secrets / mounted path via `<env_var>_FILE` or `<secrets_dir>/<env_var.lower()>`.
    2. Standard environment variable `<env_var>`.
    3. Local server config secret file `<config_dir>/<env_var.lower()>.secret`.
    """
    env_map = os.environ if env is None else env

    file_env_key = f"{env_var}_FILE"
    explicit_file = env_map.get(file_env_key)
    if explicit_file:
        secret_path = Path(explicit_file)
        if secret_path.is_file():
            val = secret_path.read_text(encoding="utf-8").strip()
            if val:
                return val

    if secrets_dir is not None:
        mount_path = secrets_dir / env_var.lower()
        if mount_path.is_file():
            val = mount_path.read_text(encoding="utf-8").strip()
            if val:
                return val

    direct = env_map.get(env_var)
    if direct is not None and direct.strip():
        return direct.strip()

    if config_dir is not None:
        cfg_path = config_dir / f"{env_var.lower()}.secret"
        if cfg_path.is_file():
            val = cfg_path.read_text(encoding="utf-8").strip()
            if val:
                return val

    return None
