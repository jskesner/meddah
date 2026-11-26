"""Official `meddah` Terminal CLI MUD client and Headless Server Management CLI."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO, cast

from app.cli.campaign_store import HeadlessLibraryStore
from app.cli.gpu_and_service import install_systemd_service, run_gpu_check
from app.cli.models import AiProviderChoice, MudTurnResult, ServerMode
from app.cli.server_daemon import HeadlessRpcClient, MeddahHeadlessServer, WsMudClient


def _build_store(args: argparse.Namespace) -> HeadlessLibraryStore:
    data_dir = Path(str(getattr(args, "data_dir", "./data")))
    raw_ai = str(getattr(args, "ai_provider", os.environ.get("AI_PROVIDER", "none")))
    ai_provider: AiProviderChoice = (
        cast(AiProviderChoice, raw_ai)
        if raw_ai in {"none", "ollama", "openai", "anthropic", "gemini"}
        else "none"
    )
    raw_mode = str(getattr(args, "mode", os.environ.get("MEDDAH_SERVER_MODE", "table")))
    server_mode: ServerMode = "guild-server" if raw_mode == "guild-server" else "table"
    return HeadlessLibraryStore(data_dir, server_mode=server_mode, ai_provider=ai_provider)


def _make_rpc(args: argparse.Namespace) -> HeadlessRpcClient:
    server_url = cast(str | None, getattr(args, "server", None)) or os.environ.get(
        "MEDDAH_SERVER_URL"
    )
    sock_raw = cast(str | None, getattr(args, "admin_sock", None)) or os.environ.get(
        "MEDDAH_ADMIN_SOCK"
    )
    admin_sock = Path(sock_raw) if sock_raw else None
    token = cast(str | None, getattr(args, "token", None)) or os.environ.get("MEDDAH_ADMIN_TOKEN")
    if (admin_sock is not None and admin_sock.exists()) or server_url:
        return HeadlessRpcClient(server_url=server_url, admin_sock=admin_sock, token=token)
    return HeadlessRpcClient(store=_build_store(args))


def _emit(out: TextIO, data: object, *, as_json: bool) -> None:
    if as_json:
        out.write(json.dumps(data, indent=2) + "\n")
    elif isinstance(data, str):
        out.write(data + "\n")
    else:
        out.write(json.dumps(data, indent=2) + "\n")


def _print_turn(out: TextIO, turn: MudTurnResult, *, as_json: bool) -> None:
    if as_json:
        out.write(turn.model_dump_json() + "\n")
        return
    for ln in turn.output_lines:
        out.write(ln + "\n")


def _run_attach(
    args: argparse.Namespace,
    *,
    stdin: TextIO,
    stdout: TextIO,
    as_json: bool,
) -> int:
    script_path = cast(str | None, getattr(args, "script", None))
    commands: list[str] | None = None
    if script_path is not None:
        raw_lines = Path(script_path).read_text(encoding="utf-8").splitlines()
        commands = [ln.strip() for ln in raw_lines if ln.strip() and not ln.strip().startswith("#")]

    server_url = cast(str | None, getattr(args, "server", None))
    sock_raw = cast(str | None, getattr(args, "admin_sock", None))
    token = cast(str | None, getattr(args, "token", None)) or os.environ.get("MEDDAH_ADMIN_TOKEN")
    campaign_id = cast(str | None, getattr(args, "campaign", None))
    ruleset_id = cast(str, getattr(args, "ruleset", "classic_d20_fantasy"))

    # Remote WebSocket attach
    if server_url:
        ws = WsMudClient(server_url, token=token)
        ws.connect()
        try:
            intro = ws.send_command("look", campaign_id=campaign_id)
            _print_turn(stdout, intro, as_json=as_json)
            line_iter = iter(commands) if commands is not None else stdin
            for raw in line_iter:
                cmd = raw.strip()
                if not cmd:
                    continue
                if cmd.lower() in {"quit", "exit"}:
                    break
                turn = ws.send_command(cmd, campaign_id=campaign_id)
                _print_turn(stdout, turn, as_json=as_json)
        finally:
            ws.close()
        return 0

    # Local UNIX socket attach
    if sock_raw and Path(sock_raw).exists():
        rpc = HeadlessRpcClient(admin_sock=Path(sock_raw), token=token)
        intro_obj = rpc.call("mud.command", {"command": "look", "campaign_id": campaign_id})
        _print_turn(stdout, MudTurnResult.model_validate(intro_obj), as_json=as_json)
        line_iter = iter(commands) if commands is not None else stdin
        for raw in line_iter:
            cmd = raw.strip()
            if not cmd:
                continue
            if cmd.lower() in {"quit", "exit"}:
                break
            turn_obj = rpc.call("mud.command", {"command": cmd, "campaign_id": campaign_id})
            _print_turn(stdout, MudTurnResult.model_validate(turn_obj), as_json=as_json)
        return 0

    # Standalone local attach (creates/resumes solo campaign cleanly)
    store = _build_store(args)
    target_cid = campaign_id
    if target_cid is None:
        existing = store.list_campaigns()
        if existing:
            target_cid = existing[0].campaign_id
        else:
            target_cid = "ashfall_solo"
            store.create_campaign(target_cid, "The Sunken Crypt of Ashfall", ruleset_id)
    else:
        known = {c.campaign_id for c in store.list_campaigns()}
        if target_cid not in known:
            store.create_campaign(target_cid, f"Campaign {target_cid}", ruleset_id)

    store.start_session(target_cid)
    eng = store.active_engine
    assert eng is not None
    if getattr(args, "manual_roll", False):
        eng.manual_roll_mode = True
    actor_name = cast(str | None, getattr(args, "actor_name", None))
    if actor_name:
        lead = eng.state.entities["pc_lead"].model_copy(update={"name": actor_name})
        ents = dict(eng.state.entities)
        ents["pc_lead"] = lead
        eng.state = eng.state.model_copy(update={"entities": ents})
        eng.initial_state = eng.initial_state.model_copy(
            update={"entities": {**eng.initial_state.entities, "pc_lead": lead}}
        )

    intro = eng.execute_command("look")
    _print_turn(stdout, intro, as_json=as_json)

    line_iter = iter(commands) if commands is not None else stdin
    for raw in line_iter:
        cmd = raw.strip()
        if not cmd:
            continue
        if cmd.lower() in {"quit", "exit"}:
            break
        turn = eng.execute_command(cmd)
        _print_turn(stdout, turn, as_json=as_json)

    store.end_session(label="attach_exit")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the complete `meddah` argparse command hierarchy."""
    parser = argparse.ArgumentParser(
        prog="meddah",
        description="Meddah: Universal Story Engine CLI & Headless Server",
    )
    parser.add_argument("--data-dir", default=os.environ.get("MEDDAH_DATA_DIR", "./data"))
    parser.add_argument("--server", default=None, help="Remote server URL (https://...)")
    parser.add_argument("--admin-sock", default=None, help="Local UNIX domain admin socket path")
    parser.add_argument("--token", default=None, help="Admin or Seat Bearer token")
    parser.add_argument("--json", action="store_true", help="Emit structured JSON responses")

    sub = parser.add_subparsers(dest="command", required=True)

    # meddah serve
    p_serve = sub.add_parser("serve", help="Start authoritative headless server daemon")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8765)
    p_serve.add_argument("--campaign", default=None)
    p_serve.add_argument("--ruleset", default="classic_d20_fantasy")
    p_serve.add_argument("--ai-provider", default="none")
    p_serve.add_argument("--mode", choices=["table", "guild-server"], default="table")
    p_serve.add_argument("--serve-web-client", action="store_true")
    p_serve.add_argument("--admin-sock", default=None)

    # meddah attach
    p_attach = sub.add_parser("attach", help="Attach interactive Terminal CLI MUD client")
    p_attach.add_argument("--campaign", default=None)
    p_attach.add_argument("--ruleset", default="classic_d20_fantasy")
    p_attach.add_argument("--actor-name", default=None)
    p_attach.add_argument("--manual-roll", action="store_true")
    p_attach.add_argument("--script", default=None, help="Non-interactive command script file")
    p_attach.add_argument("--server", default=None)
    p_attach.add_argument("--admin-sock", default=None)
    p_attach.add_argument("--token", default=None)

    # meddah campaign ...
    p_camp = sub.add_parser("campaign", help="Manage multi-campaign disk library")
    camp_sub = p_camp.add_subparsers(dest="subcommand", required=True)
    camp_sub.add_parser("list")
    p_cc = camp_sub.add_parser("create")
    p_cc.add_argument("campaign_id")
    p_cc.add_argument("--name", default=None)
    p_cc.add_argument("--ruleset", default="classic_d20_fantasy")
    p_ci = camp_sub.add_parser("import")
    p_ci.add_argument("archive_path")
    p_ci.add_argument("--campaign-id", default=None)
    p_ce = camp_sub.add_parser("export")
    p_ce.add_argument("campaign_id")
    p_ce.add_argument("output_path")
    p_cinfo = camp_sub.add_parser("info")
    p_cinfo.add_argument("campaign_id")
    p_cdel = camp_sub.add_parser("delete")
    p_cdel.add_argument("campaign_id")

    # meddah session ...
    p_sess = sub.add_parser("session", help="Control the hot-swappable active session")
    sess_sub = p_sess.add_subparsers(dest="subcommand", required=True)
    sess_sub.add_parser("status")
    p_ss = sess_sub.add_parser("start")
    p_ss.add_argument("campaign_id")
    p_ssw = sess_sub.add_parser("switch")
    p_ssw.add_argument("campaign_id")
    sess_sub.add_parser("wrap-up")
    sess_sub.add_parser("end")
    p_scp = sess_sub.add_parser("checkpoint")
    p_scp.add_argument("--label", default="manual")
    p_srw = sess_sub.add_parser("rewind")
    p_srw.add_argument("event_seq", type=int)
    p_sbk = sess_sub.add_parser("backup")
    p_sbk.add_argument("--campaign", default=None)
    p_sbk.add_argument("--out-dir", default=None)

    # meddah seat ...
    p_seat = sub.add_parser("seat", help="Manage table seats & Bearer tokens")
    seat_sub = p_seat.add_subparsers(dest="subcommand", required=True)
    seat_sub.add_parser("list")
    p_si = seat_sub.add_parser("invite")
    p_si.add_argument("--role", default="player")
    p_si.add_argument("--label", default="Guest")
    p_si.add_argument("--approve", action="store_true")
    p_sa = seat_sub.add_parser("approve")
    p_sa.add_argument("seat_id")
    p_sk = seat_sub.add_parser("kick")
    p_sk.add_argument("seat_id")
    p_sr = seat_sub.add_parser("revoke")
    p_sr.add_argument("target")

    # meddah ruleset ...
    p_rs = sub.add_parser("ruleset", help="List, import & validate .rpgrules bundles")
    rs_sub = p_rs.add_subparsers(dest="subcommand", required=True)
    rs_sub.add_parser("list")
    p_rsi = rs_sub.add_parser("import")
    p_rsi.add_argument("path")
    p_rsv = rs_sub.add_parser("validate")
    p_rsv.add_argument("path")

    # meddah backup
    p_bk = sub.add_parser("backup", help="Create a .rpgcampaign backup archive")
    p_bk.add_argument("--campaign", default=None)
    p_bk.add_argument("--out-dir", default=None)

    # meddah admin rotate-token
    p_adm = sub.add_parser("admin", help="Server administration utilities")
    adm_sub = p_adm.add_subparsers(dest="subcommand", required=True)
    adm_sub.add_parser("rotate-token")

    # meddah service install-systemd
    p_svc = sub.add_parser("service", help="Generate systemd units")
    svc_sub = p_svc.add_subparsers(dest="subcommand", required=True)
    p_sysd = svc_sub.add_parser("install-systemd")
    p_sysd.add_argument("--user", action="store_true")
    p_sysd.add_argument("--output", default=None)
    p_sysd.add_argument("--host", default="0.0.0.0")
    p_sysd.add_argument("--port", type=int, default=8420)

    # meddah gpu-check
    p_gpu = sub.add_parser("gpu-check", help="Detect NVIDIA/AMD/Vulkan GPU & Ollama profile")
    p_gpu.add_argument("--setup-rocm", action="store_true")

    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Entrypoint for the `meddah` terminal CLI and headless server daemon."""
    in_stream = stdin or sys.stdin
    out_stream = stdout or sys.stdout
    err_stream = stderr or sys.stderr
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    as_json = bool(args.json)

    try:
        if args.command == "attach":
            return _run_attach(args, stdin=in_stream, stdout=out_stream, as_json=as_json)

        if args.command == "serve":
            store = _build_store(args)
            token = store.ensure_admin_token()
            if args.campaign:
                known = {c.campaign_id for c in store.list_campaigns()}
                if args.campaign not in known:
                    store.create_campaign(args.campaign, args.campaign, args.ruleset)
                store.start_session(args.campaign)
            sock = Path(args.admin_sock) if args.admin_sock else None
            srv = MeddahHeadlessServer(
                store,
                host=args.host,
                port=args.port,
                admin_sock=sock,
                serve_web_client=bool(args.serve_web_client),
            )
            out_stream.write(
                f"Starting Meddah server on http://{args.host}:{args.port} "
                f"(mode={store.server_mode}, ai={store.ai_provider}, admin_token={token[:10]}...)\n"
            )
            asyncio.run(srv.serve_forever())
            return 0

        if args.command == "gpu-check":
            report = run_gpu_check(setup_rocm=bool(args.setup_rocm))
            _emit(out_stream, report.model_dump(mode="json"), as_json=True)
            return 0

        if args.command == "service" and args.subcommand == "install-systemd":
            dest = install_systemd_service(
                data_dir=Path(args.data_dir),
                output_path=Path(args.output) if args.output else None,
                host=args.host,
                port=args.port,
                user_mode=bool(args.user or not args.output),
            )
            _emit(out_stream, {"systemd_unit": str(dest)}, as_json=as_json)
            return 0

        rpc = _make_rpc(args)

        if args.command == "campaign":
            if args.subcommand == "list":
                _emit(out_stream, rpc.call("campaign.list"), as_json=as_json)
            elif args.subcommand == "create":
                res = rpc.call(
                    "campaign.create",
                    {
                        "campaign_id": args.campaign_id,
                        "name": args.name or args.campaign_id,
                        "ruleset": args.ruleset,
                    },
                )
                _emit(out_stream, res, as_json=as_json)
            elif args.subcommand == "import":
                res = rpc.call(
                    "campaign.import",
                    {"archive_path": args.archive_path, "campaign_id": args.campaign_id},
                )
                _emit(out_stream, res, as_json=as_json)
            elif args.subcommand == "export":
                res = rpc.call(
                    "campaign.export",
                    {"campaign_id": args.campaign_id, "output_path": args.output_path},
                )
                _emit(out_stream, res, as_json=as_json)
            elif args.subcommand == "info":
                _emit(
                    out_stream,
                    rpc.call("campaign.info", {"campaign_id": args.campaign_id}),
                    as_json=as_json,
                )
            elif args.subcommand == "delete":
                _emit(
                    out_stream,
                    rpc.call("campaign.delete", {"campaign_id": args.campaign_id}),
                    as_json=as_json,
                )
            return 0

        if args.command == "session":
            if args.subcommand == "status":
                _emit(out_stream, rpc.call("session.status"), as_json=as_json)
            elif args.subcommand == "start":
                _emit(
                    out_stream,
                    rpc.call("session.start", {"campaign_id": args.campaign_id}),
                    as_json=as_json,
                )
            elif args.subcommand == "switch":
                _emit(
                    out_stream,
                    rpc.call("session.switch", {"campaign_id": args.campaign_id}),
                    as_json=as_json,
                )
            elif args.subcommand == "wrap-up":
                _emit(out_stream, rpc.call("session.wrap_up"), as_json=as_json)
            elif args.subcommand == "end":
                _emit(out_stream, rpc.call("session.end"), as_json=as_json)
            elif args.subcommand == "checkpoint":
                _emit(
                    out_stream,
                    rpc.call("session.checkpoint", {"label": args.label}),
                    as_json=as_json,
                )
            elif args.subcommand == "rewind":
                _emit(
                    out_stream,
                    rpc.call("session.rewind", {"event_seq": args.event_seq}),
                    as_json=as_json,
                )
            elif args.subcommand == "backup":
                _emit(
                    out_stream,
                    rpc.call(
                        "session.backup",
                        {"campaign_id": args.campaign, "out_dir": args.out_dir},
                    ),
                    as_json=as_json,
                )
            return 0

        if args.command == "backup":
            _emit(
                out_stream,
                rpc.call(
                    "session.backup",
                    {"campaign_id": args.campaign, "out_dir": args.out_dir},
                ),
                as_json=as_json,
            )
            return 0

        if args.command == "seat":
            if args.subcommand == "list":
                _emit(out_stream, rpc.call("seat.list"), as_json=as_json)
            elif args.subcommand == "invite":
                _emit(
                    out_stream,
                    rpc.call(
                        "seat.invite",
                        {
                            "role": args.role,
                            "label": args.label,
                            "auto_approve": bool(args.approve),
                        },
                    ),
                    as_json=as_json,
                )
            elif args.subcommand == "approve":
                _emit(
                    out_stream,
                    rpc.call("seat.approve", {"seat_id": args.seat_id}),
                    as_json=as_json,
                )
            elif args.subcommand == "kick":
                _emit(
                    out_stream,
                    rpc.call("seat.kick", {"seat_id": args.seat_id}),
                    as_json=as_json,
                )
            elif args.subcommand == "revoke":
                _emit(
                    out_stream,
                    rpc.call("seat.revoke", {"target": args.target}),
                    as_json=as_json,
                )
            return 0

        if args.command == "ruleset":
            if args.subcommand == "list":
                _emit(out_stream, rpc.call("ruleset.list"), as_json=as_json)
            elif args.subcommand == "import":
                _emit(
                    out_stream,
                    rpc.call("ruleset.import", {"path": args.path}),
                    as_json=as_json,
                )
            elif args.subcommand == "validate":
                _emit(
                    out_stream,
                    rpc.call("ruleset.validate", {"path": args.path}),
                    as_json=as_json,
                )
            return 0

        if args.command == "admin" and args.subcommand == "rotate-token":
            _emit(out_stream, rpc.call("admin.rotate_token"), as_json=as_json)
            return 0

    except (KeyError, ValueError, RuntimeError, FileNotFoundError, PermissionError) as exc:
        err_stream.write(f"Error: {exc}\n")
        return 1

    return 0
