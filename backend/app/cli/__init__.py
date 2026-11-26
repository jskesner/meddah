"""Layer 4: Terminal MUD client and headless server administration CLI."""

from app.cli.campaign_store import HeadlessLibraryStore
from app.cli.gpu_and_service import install_systemd_service, render_systemd_unit, run_gpu_check
from app.cli.main import build_parser, main
from app.cli.models import (
    AiProviderChoice,
    CampaignMetadata,
    CheckpointSummary,
    GpuProbeReport,
    HeadlessSeatRole,
    MudTurnResult,
    RoomNodeSpec,
    SeatRecord,
    SeatStatus,
    ServerMode,
    SessionStatusSnapshot,
    resolve_headless_secret,
)
from app.cli.mud_session import MudSessionEngine
from app.cli.server_daemon import (
    HeadlessRpcClient,
    MeddahHeadlessServer,
    WsMudClient,
    dispatch_rpc_method,
)
from app.cli.starter_adventure import bootstrap_entities_for_ruleset, build_ashfall_rooms

__all__ = [
    "AiProviderChoice",
    "CampaignMetadata",
    "CheckpointSummary",
    "GpuProbeReport",
    "HeadlessLibraryStore",
    "HeadlessRpcClient",
    "HeadlessSeatRole",
    "MeddahHeadlessServer",
    "MudSessionEngine",
    "MudTurnResult",
    "RoomNodeSpec",
    "SeatRecord",
    "SeatStatus",
    "ServerMode",
    "SessionStatusSnapshot",
    "WsMudClient",
    "bootstrap_entities_for_ruleset",
    "build_ashfall_rooms",
    "build_parser",
    "dispatch_rpc_method",
    "install_systemd_service",
    "main",
    "render_systemd_unit",
    "resolve_headless_secret",
    "run_gpu_check",
]
