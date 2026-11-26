"""Multi-campaign disk library, hot-swappable active session, seats, backups & tokens."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import shutil
import stat
import zipfile
from collections.abc import Mapping
from pathlib import Path
from typing import cast

from app.cli.models import (
    AiProviderChoice,
    CampaignMetadata,
    CheckpointSummary,
    HeadlessSeatRole,
    SeatRecord,
    ServerMode,
    SessionStatusSnapshot,
    resolve_headless_secret,
)
from app.cli.mud_session import MudSessionEngine
from app.ingestion import import_ruleset_data, import_ruleset_file, lint_ruleset_schema
from app.ruleset_vm import PackageManifest, RulesetSchema, replay_events, state_hash

DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[3]


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _safe_id(raw_id: str, label: str = "identifier") -> str:
    cleaned = raw_id.strip()
    if (
        not cleaned
        or "/" in cleaned
        or "\\" in cleaned
        or ".." in cleaned
        or cleaned.startswith(".")
    ):
        raise ValueError(f"Unsafe {label}: {raw_id!r}")
    return cleaned


def _safe_extract_campaign_zip(archive_path: Path) -> dict[str, dict[str, object]]:
    """Safely extract JSON files from a .rpgcampaign zip preventing Zip-Slip & symlinks."""
    if not archive_path.is_file():
        raise FileNotFoundError(f"Campaign archive not found: {archive_path}")
    extracted: dict[str, dict[str, object]] = {}
    with zipfile.ZipFile(archive_path, "r") as zf:
        total_uncompressed = 0
        for info in zf.infolist():
            mode = (info.external_attr >> 16) & 0xFFFF
            if stat.S_ISLNK(mode):
                raise ValueError(
                    f"Symlink entries are forbidden in campaign archive: {info.filename}"
                )
            member = info.filename
            if member.startswith("/") or member.startswith("\\") or ".." in Path(member).parts:
                raise ValueError(f"Unsafe path in campaign archive: {member!r}")
            total_uncompressed += info.file_size
            if total_uncompressed > 50 * 1024 * 1024:
                raise ValueError("Campaign archive exceeds 50 MB uncompressed limit.")
            if not info.is_dir() and member.endswith(".json"):
                raw_obj = json.loads(zf.read(info).decode("utf-8"))
                if not isinstance(raw_obj, dict):
                    raise ValueError(f"Expected JSON object in '{member}'.")
                extracted[member] = cast(dict[str, object], raw_obj)
    return extracted


class HeadlessLibraryStore:
    """Manages multi-campaign disk storage, one active session, seats, rulesets & backups."""

    def __init__(
        self,
        data_dir: Path,
        *,
        sample_rulesets_dir: Path | None = None,
        server_mode: ServerMode = "table",
        ai_provider: AiProviderChoice = "none",
    ) -> None:
        self.data_dir = Path(data_dir).resolve()
        self.campaigns_dir = self.data_dir / "campaigns"
        self.rulesets_dir = self.data_dir / "rulesets"
        self.backups_dir = self.data_dir / "backups"
        self.config_dir = self.data_dir / "config"
        self.logs_dir = self.data_dir / "logs"
        for sub in (
            self.campaigns_dir,
            self.rulesets_dir,
            self.backups_dir,
            self.config_dir,
            self.logs_dir,
        ):
            sub.mkdir(parents=True, exist_ok=True)

        default_samples = DEFAULT_REPO_ROOT / "sample_rulesets"
        self.sample_rulesets_dir: Path | None = (
            sample_rulesets_dir
            if sample_rulesets_dir is not None
            else (default_samples if default_samples.is_dir() else None)
        )
        self.server_mode: ServerMode = server_mode
        self.ai_provider: AiProviderChoice = ai_provider
        self._active_engine: MudSessionEngine | None = None
        self._seats_file = self.config_dir / "seats.json"
        self._ensure_default_host_seat()

    def _ensure_default_host_seat(self) -> None:
        if not self._seats_file.is_file():
            host = SeatRecord(
                seat_id="seat_host",
                label="Host GM",
                role="host",
                status="approved",
                token_hash=_hash_token("local_unix_socket_host"),
                entity_id="pc_lead",
            )
            self._save_seats({"seat_host": host})

    def _load_seats(self) -> dict[str, SeatRecord]:
        if not self._seats_file.is_file():
            return {}
        raw = json.loads(self._seats_file.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return {}
        return {str(k): SeatRecord.model_validate(v) for k, v in raw.items()}

    def _save_seats(self, seats: Mapping[str, SeatRecord]) -> None:
        serialized = {k: v.model_dump(mode="json") for k, v in sorted(seats.items())}
        self._seats_file.write_text(json.dumps(serialized, indent=2), encoding="utf-8")

    # ------------------------------------------------------------------
    # Admin Token & Secrets
    # ------------------------------------------------------------------

    def get_configured_admin_token(self) -> str | None:
        """Return currently active admin token from env, Docker secret mount, or local file."""
        return resolve_headless_secret("MEDDAH_ADMIN_TOKEN", config_dir=self.config_dir)

    def ensure_admin_token(self) -> str:
        """Return existing admin token or generate and persist a fresh high-entropy token."""
        existing = self.get_configured_admin_token()
        if existing:
            return existing
        token = f"mdh_adm_{secrets.token_urlsafe(24)}"
        secret_file = self.config_dir / "meddah_admin_token.secret"
        secret_file.write_text(token, encoding="utf-8")
        return token

    def rotate_admin_token(self) -> str:
        """Generate and persist a rotated high-entropy MEDDAH_ADMIN_TOKEN."""
        token = f"mdh_adm_{secrets.token_urlsafe(24)}"
        secret_file = self.config_dir / "meddah_admin_token.secret"
        secret_file.write_text(token, encoding="utf-8")
        return token

    def verify_admin_token(self, candidate: str | None) -> bool:
        """Constant-time comparison against active admin token."""
        if not candidate:
            return False
        expected = self.get_configured_admin_token()
        if not expected:
            return False
        return hmac.compare_digest(candidate.strip(), expected)

    # ------------------------------------------------------------------
    # Ruleset Library Management
    # ------------------------------------------------------------------

    def _discover_ruleset_files(self) -> dict[str, Path]:
        found: dict[str, Path] = {}
        search_roots: list[Path] = []
        if self.sample_rulesets_dir is not None and self.sample_rulesets_dir.is_dir():
            search_roots.append(self.sample_rulesets_dir)
        search_roots.append(self.rulesets_dir)

        for root in search_roots:
            for path in sorted(root.rglob("*.json")):
                if path.name in {"creation.json", "advancement.json", "scenarios.json"}:
                    continue
                try:
                    raw = json.loads(path.read_text(encoding="utf-8"))
                    if isinstance(raw, dict) and isinstance(raw.get("manifest"), dict):
                        manifest = PackageManifest.model_validate(raw["manifest"])
                        if manifest.package_type == "ruleset":
                            found[manifest.package_id] = path
                except Exception:
                    continue
        for rp in sorted(self.rulesets_dir.glob("*.rpgrules")):
            try:
                ruleset, _ = import_ruleset_file(rp)
                found[ruleset.manifest.package_id] = rp
            except Exception:
                continue
        return found

    def list_rulesets(self) -> list[dict[str, object]]:
        """List discovered and imported rulesets with package_id, name, version & hash."""
        entries: list[dict[str, object]] = []
        for pkg_id, path in sorted(self._discover_ruleset_files().items()):
            try:
                ruleset, _ = import_ruleset_file(path)
                entries.append(
                    {
                        "package_id": pkg_id,
                        "name": ruleset.manifest.name,
                        "version": ruleset.manifest.version,
                        "ruleset_hash": ruleset.content_hash(),
                        "path": str(path),
                    }
                )
            except Exception:
                continue
        return entries

    def load_ruleset(self, ruleset_id_or_path: str) -> tuple[RulesetSchema, Path]:
        """Resolve a ruleset by package_id or filesystem path."""
        candidate = Path(ruleset_id_or_path)
        if candidate.is_file():
            ruleset, _ = import_ruleset_file(candidate)
            return ruleset, candidate
        discovered = self._discover_ruleset_files()
        if ruleset_id_or_path not in discovered:
            raise KeyError(
                f"Unknown ruleset '{ruleset_id_or_path}'. Available: {sorted(discovered)}"
            )
        path = discovered[ruleset_id_or_path]
        ruleset, _ = import_ruleset_file(path)
        return ruleset, path

    def import_ruleset(self, source_path: Path) -> dict[str, object]:
        """Validate and copy a .rpgrules or ruleset.json file into <data_dir>/rulesets/."""
        ruleset, warnings = import_ruleset_file(source_path)
        pkg_id = _safe_id(ruleset.manifest.package_id, "package_id")
        dest = self.rulesets_dir / f"{pkg_id}.json"
        dest.write_text(ruleset.model_dump_json(indent=2), encoding="utf-8")
        return {
            "package_id": pkg_id,
            "name": ruleset.manifest.name,
            "ruleset_hash": ruleset.content_hash(),
            "path": str(dest),
            "warnings": list(warnings),
        }

    def validate_ruleset(self, target: Path | str) -> dict[str, object]:
        """Run deterministic importer, graph validation, and Phase 2B static linter."""
        path = Path(target)
        ruleset, import_warnings = (
            import_ruleset_file(path) if path.is_file() else (self.load_ruleset(str(target))[0], ())
        )
        graph_errors = ruleset.validate_graph()
        lint_report = lint_ruleset_schema(ruleset)
        return {
            "package_id": ruleset.manifest.package_id,
            "ruleset_hash": ruleset.content_hash(),
            "valid": lint_report.is_valid and not graph_errors,
            "graph_errors": list(graph_errors),
            "lint_diagnostics": [d.model_dump(mode="json") for d in lint_report.diagnostics],
            "import_warnings": list(import_warnings),
        }

    # ------------------------------------------------------------------
    # Multi-Campaign Library CRUD + Export/Import
    # ------------------------------------------------------------------

    def _campaign_dir(self, campaign_id: str) -> Path:
        cid = _safe_id(campaign_id, "campaign_id")
        return self.campaigns_dir / cid

    def list_campaigns(self) -> list[CampaignMetadata]:
        """Return all stored campaigns sorted by created_order and campaign_id."""
        items: list[CampaignMetadata] = []
        for meta_path in sorted(self.campaigns_dir.glob("*/campaign.json")):
            raw = json.loads(meta_path.read_text(encoding="utf-8"))
            items.append(CampaignMetadata.model_validate(raw))
        items.sort(key=lambda c: (c.created_order, c.campaign_id))
        return items

    def get_campaign_info(self, campaign_id: str) -> dict[str, object]:
        """Return stored metadata, snapshot event count, and checkpoints for one campaign."""
        cdir = self._campaign_dir(campaign_id)
        meta_path = cdir / "campaign.json"
        if not meta_path.is_file():
            raise KeyError(f"Unknown campaign '{campaign_id}'.")
        meta = CampaignMetadata.model_validate_json(meta_path.read_text(encoding="utf-8"))
        snap_path = cdir / "session_snapshot.json"
        event_seq = 0
        checkpoints: list[object] = []
        if snap_path.is_file():
            snap = json.loads(snap_path.read_text(encoding="utf-8"))
            if isinstance(snap, dict):
                raw_state = snap.get("state")
                if isinstance(raw_state, dict):
                    event_seq = int(raw_state.get("event_seq", 0))
                raw_cps = snap.get("checkpoints")
                if isinstance(raw_cps, list):
                    checkpoints = raw_cps
        return {
            **meta.model_dump(mode="json"),
            "event_seq": event_seq,
            "checkpoint_count": len(checkpoints),
            "active": (
                self._active_engine is not None
                and self._active_engine.campaign.campaign_id == meta.campaign_id
            ),
        }

    def create_campaign(
        self,
        campaign_id: str,
        name: str,
        ruleset_id_or_path: str,
        *,
        scene_seed: str | None = None,
        description: str = "",
    ) -> CampaignMetadata:
        """Create and initialize a playable campaign pinned to a validated ruleset."""
        cid = _safe_id(campaign_id, "campaign_id")
        cdir = self._campaign_dir(cid)
        if cdir.exists():
            raise ValueError(f"Campaign '{cid}' already exists.")

        ruleset, ruleset_path = self.load_ruleset(ruleset_id_or_path)
        existing_count = len(self.list_campaigns())
        meta = CampaignMetadata(
            campaign_id=cid,
            name=name.strip() or cid,
            ruleset_id=ruleset.manifest.package_id,
            ruleset_hash=ruleset.content_hash(),
            ruleset_path=str(ruleset_path),
            scene_seed=scene_seed or f"seed_{cid}",
            description=description,
            created_order=existing_count + 1,
        )
        cdir.mkdir(parents=True, exist_ok=True)
        (cdir / "campaign.json").write_text(meta.model_dump_json(indent=2), encoding="utf-8")
        (cdir / "ruleset.json").write_text(ruleset.model_dump_json(indent=2), encoding="utf-8")

        engine = MudSessionEngine(meta, ruleset)
        engine.create_checkpoint(label="initial_bootstrap")
        (cdir / "session_snapshot.json").write_text(
            json.dumps(engine.to_snapshot_dict(), indent=2),
            encoding="utf-8",
        )
        return meta

    def delete_campaign(self, campaign_id: str) -> None:
        """Delete a stored campaign folder; detaches active engine first if loaded."""
        cid = _safe_id(campaign_id, "campaign_id")
        cdir = self._campaign_dir(cid)
        if not cdir.is_dir():
            raise KeyError(f"Unknown campaign '{cid}'.")
        if self._active_engine is not None and self._active_engine.campaign.campaign_id == cid:
            self._active_engine = None
        shutil.rmtree(cdir)

    def export_campaign(self, campaign_id: str, output_path: Path) -> Path:
        """Export a self-contained portable .rpgcampaign archive with ruleset & event log."""
        cid = _safe_id(campaign_id, "campaign_id")
        cdir = self._campaign_dir(cid)
        if not (cdir / "campaign.json").is_file():
            raise KeyError(f"Unknown campaign '{cid}'.")
        if self._active_engine is not None and self._active_engine.campaign.campaign_id == cid:
            self._persist_active_engine()
        dest = Path(output_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for fname in ("campaign.json", "ruleset.json", "session_snapshot.json"):
                fp = cdir / fname
                if fp.is_file():
                    zf.write(fp, arcname=fname)
        return dest

    def import_campaign(
        self,
        archive_path: Path,
        *,
        override_campaign_id: str | None = None,
    ) -> CampaignMetadata:
        """Safely import a .rpgcampaign archive and verify ruleset hash & replay integrity."""
        files = _safe_extract_campaign_zip(Path(archive_path))
        if "campaign.json" not in files or "ruleset.json" not in files:
            raise ValueError("Campaign archive missing required campaign.json or ruleset.json.")
        meta = CampaignMetadata.model_validate(files["campaign.json"])
        ruleset, _ = import_ruleset_data(files["ruleset.json"], source_name=archive_path.name)
        if ruleset.content_hash() != meta.ruleset_hash:
            raise ValueError(
                "Campaign ruleset hash mismatch in archive "
                f"({ruleset.content_hash()} != {meta.ruleset_hash})."
            )
        target_cid = _safe_id(override_campaign_id or meta.campaign_id, "campaign_id")
        cdir = self._campaign_dir(target_cid)
        if cdir.exists():
            raise ValueError(f"Campaign '{target_cid}' already exists.")

        updated_meta = meta.model_copy(update={"campaign_id": target_cid})
        if "session_snapshot.json" in files:
            snap_payload = dict(files["session_snapshot.json"])
            snap_payload["campaign"] = updated_meta.model_dump(mode="json")
            engine = MudSessionEngine.from_snapshot_dict(snap_payload, ruleset)
            replayed = replay_events(ruleset, engine.initial_state, engine.event_log)
            if state_hash(replayed) != state_hash(engine.state):
                raise ValueError("Campaign event log failed deterministic replay verification.")
        else:
            engine = MudSessionEngine(updated_meta, ruleset)

        cdir.mkdir(parents=True, exist_ok=True)
        (cdir / "campaign.json").write_text(
            updated_meta.model_dump_json(indent=2), encoding="utf-8"
        )
        (cdir / "ruleset.json").write_text(ruleset.model_dump_json(indent=2), encoding="utf-8")
        (cdir / "session_snapshot.json").write_text(
            json.dumps(engine.to_snapshot_dict(), indent=2),
            encoding="utf-8",
        )
        return updated_meta

    # ------------------------------------------------------------------
    # Hot-Swappable Active Session Lifecycle & Backups
    # ------------------------------------------------------------------

    def _load_engine_from_disk(self, campaign_id: str) -> MudSessionEngine:
        cid = _safe_id(campaign_id, "campaign_id")
        cdir = self._campaign_dir(cid)
        if not (cdir / "campaign.json").is_file():
            raise KeyError(f"Unknown campaign '{cid}'.")
        meta = CampaignMetadata.model_validate_json((cdir / "campaign.json").read_text("utf-8"))
        ruleset, _ = import_ruleset_file(cdir / "ruleset.json")
        snap_path = cdir / "session_snapshot.json"
        if snap_path.is_file():
            snap_raw = json.loads(snap_path.read_text(encoding="utf-8"))
            if isinstance(snap_raw, dict):
                return MudSessionEngine.from_snapshot_dict(
                    cast(Mapping[str, object], snap_raw),
                    ruleset,
                )
        return MudSessionEngine(meta, ruleset)

    def _persist_active_engine(self) -> None:
        if self._active_engine is None:
            return
        cid = self._active_engine.campaign.campaign_id
        cdir = self._campaign_dir(cid)
        cdir.mkdir(parents=True, exist_ok=True)
        (cdir / "session_snapshot.json").write_text(
            json.dumps(self._active_engine.to_snapshot_dict(), indent=2),
            encoding="utf-8",
        )

    @property
    def active_engine(self) -> MudSessionEngine | None:
        """Return currently loaded hot-swappable MudSessionEngine if active."""
        return self._active_engine

    def start_session(self, campaign_id: str) -> SessionStatusSnapshot:
        """Start (or resume) the specified campaign as the single active session."""
        if self._active_engine is not None:
            self._persist_active_engine()
        self._active_engine = self._load_engine_from_disk(campaign_id)
        self._persist_active_engine()
        return self.session_status()

    def switch_session(self, campaign_id: str) -> SessionStatusSnapshot:
        """Checkpoint the current active campaign and hot-swap cleanly to another campaign."""
        if self._active_engine is not None:
            self._active_engine.create_checkpoint(label="auto_switch")
            self._persist_active_engine()
        self._active_engine = self._load_engine_from_disk(campaign_id)
        self._persist_active_engine()
        return self.session_status()

    def wrap_up_session(self) -> SessionStatusSnapshot:
        """Create a wrap-up checkpoint and persist active campaign state without unloading."""
        if self._active_engine is None:
            raise RuntimeError("No active session running.")
        self._active_engine.create_checkpoint(label="wrap_up")
        self._persist_active_engine()
        return self.session_status()

    def end_session(self, *, label: str = "session_end") -> SessionStatusSnapshot:
        """Create an atomic shutdown checkpoint, persist to disk, and unload active session."""
        if self._active_engine is not None:
            self._active_engine.create_checkpoint(label=label)
            self._persist_active_engine()
            self._active_engine = None
        return self.session_status()

    def checkpoint_session(self, label: str = "manual") -> CheckpointSummary:
        """Create and persist a deterministic checkpoint on the active session."""
        if self._active_engine is None:
            raise RuntimeError("No active session running.")
        cp = self._active_engine.create_checkpoint(label=label)
        self._persist_active_engine()
        return cp

    def rewind_session(self, target_event_seq: int) -> CheckpointSummary:
        """Rewind active session to an earlier event_seq via VM replay and persist."""
        if self._active_engine is None:
            raise RuntimeError("No active session running.")
        cp = self._active_engine.rewind_to_event(target_event_seq)
        self._persist_active_engine()
        return cp

    def backup_session(
        self,
        campaign_id: str | None = None,
        *,
        out_dir: Path | None = None,
    ) -> Path:
        """Write an archive backup (.rpgcampaign) into <data_dir>/backups/ or out_dir."""
        target_cid = campaign_id or (
            self._active_engine.campaign.campaign_id if self._active_engine is not None else None
        )
        if target_cid is None:
            raise RuntimeError("Specify --campaign or start an active session before backup.")
        dest_dir = Path(out_dir) if out_dir is not None else self.backups_dir
        dest_dir.mkdir(parents=True, exist_ok=True)
        existing = list(dest_dir.glob(f"{target_cid}_backup_*.rpgcampaign"))
        dest_file = dest_dir / f"{target_cid}_backup_{len(existing) + 1:04d}.rpgcampaign"
        return self.export_campaign(target_cid, dest_file)

    def session_status(self) -> SessionStatusSnapshot:
        """Return live summary of the active hot-swappable campaign session."""
        seats = self._load_seats()
        approved_count = sum(1 for s in seats.values() if s.status == "approved")
        if self._active_engine is None:
            return SessionStatusSnapshot(
                running=False,
                ai_provider=self.ai_provider,
                server_mode=self.server_mode,
                connected_seats=approved_count,
            )
        eng = self._active_engine
        return SessionStatusSnapshot(
            active_campaign_id=eng.campaign.campaign_id,
            active_campaign_name=eng.campaign.name,
            ruleset_id=eng.ruleset.manifest.package_id,
            ruleset_hash=eng.ruleset.content_hash(),
            running=True,
            event_seq=eng.state.event_seq,
            elapsed_world_seconds=eng.state.elapsed_world_seconds,
            current_room_id=eng.entity_rooms.get(eng.active_entity_id, "ashfall_courtyard"),
            manual_roll_mode=eng.manual_roll_mode,
            ai_provider=self.ai_provider,
            server_mode=self.server_mode,
            connected_seats=approved_count,
            active_entities=tuple(sorted(eng.state.entities)),
        )

    # ------------------------------------------------------------------
    # Seat & Invite Token RBAC Management
    # ------------------------------------------------------------------

    def list_seats(self) -> list[SeatRecord]:
        """List all registered seats ordered by seat_id."""
        seats = self._load_seats()
        return [seats[k] for k in sorted(seats)]

    def invite_seat(
        self,
        *,
        role: str = "player",
        label: str = "Guest",
        auto_approve: bool = False,
        entity_id: str | None = "pc_lead",
    ) -> tuple[SeatRecord, str]:
        """Create an invite token for a seat role and return (SeatRecord, raw_token)."""
        valid_roles = {"host", "gm", "co_gm", "host_player", "player", "spectator"}
        if role not in valid_roles:
            raise ValueError(f"Unsupported role '{role}'. Expected one of {sorted(valid_roles)}.")
        seats = self._load_seats()
        idx = 1
        while f"seat_{idx:03d}" in seats:
            idx += 1
        seat_id = f"seat_{idx:03d}"
        raw_token = f"mdh_seat_{secrets.token_urlsafe(18)}"
        rec = SeatRecord(
            seat_id=seat_id,
            label=label.strip() or seat_id,
            role=cast(HeadlessSeatRole, role),
            status="approved" if auto_approve else "pending",
            token_hash=_hash_token(raw_token),
            entity_id=entity_id,
        )
        seats[seat_id] = rec
        self._save_seats(seats)
        return rec, raw_token

    def approve_seat(self, seat_id: str) -> SeatRecord:
        """Approve a pending guest seat."""
        seats = self._load_seats()
        rec = seats.get(seat_id)
        if rec is None:
            raise KeyError(f"Unknown seat '{seat_id}'.")
        updated = rec.model_copy(update={"status": "approved"})
        seats[seat_id] = updated
        self._save_seats(seats)
        return updated

    def kick_seat(self, seat_id: str) -> SeatRecord:
        """Kick an active seat while allowing subsequent re-approval or re-invite."""
        seats = self._load_seats()
        rec = seats.get(seat_id)
        if rec is None:
            raise KeyError(f"Unknown seat '{seat_id}'.")
        updated = rec.model_copy(update={"status": "kicked"})
        seats[seat_id] = updated
        self._save_seats(seats)
        return updated

    def revoke_token(self, seat_or_token: str) -> SeatRecord:
        """Permanently revoke a seat credential matching seat_id or raw token."""
        seats = self._load_seats()
        target_hash = _hash_token(seat_or_token)
        for sid, rec in seats.items():
            if sid == seat_or_token or hmac.compare_digest(rec.token_hash, target_hash):
                updated = rec.model_copy(update={"status": "revoked"})
                seats[sid] = updated
                self._save_seats(seats)
                return updated
        raise KeyError(f"No matching seat or token '{seat_or_token}'.")

    def authenticate_seat_token(self, raw_token: str | None) -> SeatRecord | None:
        """Authenticate an approved seat token in constant time."""
        if not raw_token:
            return None
        candidate_hash = _hash_token(raw_token.strip())
        for rec in self._load_seats().values():
            if rec.status == "approved" and hmac.compare_digest(rec.token_hash, candidate_hash):
                return rec
        return None
