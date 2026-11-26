"""Headless HTTP/UNIX/WebSocket server daemon and RPC/WS transport clients (Phase 2.5)."""

from __future__ import annotations

import asyncio
import base64
import contextlib
import hashlib
import http.client
import json
import secrets
import signal
import socket
import struct
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from pathlib import Path
from typing import cast

from app.cli.campaign_store import HeadlessLibraryStore
from app.cli.models import MudTurnResult
from app.ruleset_vm import SeatRole

_WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def _ws_accept_key(client_key: str) -> str:
    digest = hashlib.sha1((client_key.strip() + _WS_GUID).encode("ascii")).digest()
    return base64.b64encode(digest).decode("ascii")


def _encode_ws_frame(payload: bytes, *, opcode: int = 0x1, mask: bool = False) -> bytes:
    header = bytearray([0x80 | (opcode & 0x0F)])
    length = len(payload)
    mask_bit = 0x80 if mask else 0x00
    if length < 126:
        header.append(mask_bit | length)
    elif length <= 0xFFFF:
        header.append(mask_bit | 126)
        header.extend(struct.pack("!H", length))
    else:
        header.append(mask_bit | 127)
        header.extend(struct.pack("!Q", length))

    if mask:
        mask_key = secrets.token_bytes(4)
        header.extend(mask_key)
        masked = bytes(b ^ mask_key[idx % 4] for idx, b in enumerate(payload))
        return bytes(header) + masked
    return bytes(header) + payload


async def _read_ws_frame_async(reader: asyncio.StreamReader) -> tuple[int, bytes] | None:
    try:
        first_two = await reader.readexactly(2)
    except asyncio.IncompleteReadError:
        return None
    b1, b2 = first_two[0], first_two[1]
    opcode = b1 & 0x0F
    is_masked = bool(b2 & 0x80)
    length = b2 & 0x7F
    if length == 126:
        length = struct.unpack("!H", await reader.readexactly(2))[0]
    elif length == 127:
        length = struct.unpack("!Q", await reader.readexactly(8))[0]
    mask_key = await reader.readexactly(4) if is_masked else b""
    data = await reader.readexactly(length) if length > 0 else b""
    if is_masked:
        data = bytes(b ^ mask_key[idx % 4] for idx, b in enumerate(data))
    return opcode, data


def _read_ws_frame_sync(sock: socket.socket) -> tuple[int, bytes] | None:
    def _recv_exact(n: int) -> bytes:
        chunks = bytearray()
        while len(chunks) < n:
            part = sock.recv(n - len(chunks))
            if not part:
                raise EOFError("WebSocket connection closed")
            chunks.extend(part)
        return bytes(chunks)

    try:
        first_two = _recv_exact(2)
    except EOFError:
        return None
    b1, b2 = first_two[0], first_two[1]
    opcode = b1 & 0x0F
    is_masked = bool(b2 & 0x80)
    length = b2 & 0x7F
    if length == 126:
        length = struct.unpack("!H", _recv_exact(2))[0]
    elif length == 127:
        length = struct.unpack("!Q", _recv_exact(8))[0]
    mask_key = _recv_exact(4) if is_masked else b""
    data = _recv_exact(length) if length > 0 else b""
    if is_masked:
        data = bytes(b ^ mask_key[idx % 4] for idx, b in enumerate(data))
    return opcode, data


def dispatch_rpc_method(
    store: HeadlessLibraryStore,
    method: str,
    params: Mapping[str, object] | None = None,
    *,
    seat_id: str = "seat_host",
    seat_role: SeatRole = "gm",
) -> object:
    """Execute one local or remote JSON-RPC operation against HeadlessLibraryStore."""
    args = dict(params or {})

    if method == "campaign.list":
        return [c.model_dump(mode="json") for c in store.list_campaigns()]
    if method == "campaign.create":
        meta = store.create_campaign(
            str(args["campaign_id"]),
            str(args.get("name", args["campaign_id"])),
            str(args["ruleset"]),
            scene_seed=str(args["scene_seed"]) if args.get("scene_seed") else None,
            description=str(args.get("description", "")),
        )
        return meta.model_dump(mode="json")
    if method == "campaign.info":
        return store.get_campaign_info(str(args["campaign_id"]))
    if method == "campaign.delete":
        store.delete_campaign(str(args["campaign_id"]))
        return {"deleted": str(args["campaign_id"])}
    if method == "campaign.export":
        out = store.export_campaign(str(args["campaign_id"]), Path(str(args["output_path"])))
        return {"archive_path": str(out)}
    if method == "campaign.import":
        meta = store.import_campaign(
            Path(str(args["archive_path"])),
            override_campaign_id=str(args["campaign_id"]) if args.get("campaign_id") else None,
        )
        return meta.model_dump(mode="json")

    if method == "session.status":
        return store.session_status().model_dump(mode="json")
    if method == "session.start":
        return store.start_session(str(args["campaign_id"])).model_dump(mode="json")
    if method == "session.switch":
        return store.switch_session(str(args["campaign_id"])).model_dump(mode="json")
    if method == "session.wrap_up":
        return store.wrap_up_session().model_dump(mode="json")
    if method == "session.end":
        return store.end_session().model_dump(mode="json")
    if method == "session.checkpoint":
        return store.checkpoint_session(str(args.get("label", "manual"))).model_dump(mode="json")
    if method == "session.rewind":
        return store.rewind_session(int(str(args["event_seq"]))).model_dump(mode="json")
    if method == "session.backup":
        cid = str(args["campaign_id"]) if args.get("campaign_id") else None
        out_dir = Path(str(args["out_dir"])) if args.get("out_dir") else None
        path = store.backup_session(cid, out_dir=out_dir)
        return {"backup_path": str(path)}

    if method == "seat.list":
        return [s.model_dump(mode="json") for s in store.list_seats()]
    if method == "seat.invite":
        rec, token = store.invite_seat(
            role=str(args.get("role", "player")),
            label=str(args.get("label", "Guest")),
            auto_approve=bool(args.get("auto_approve", False)),
        )
        return {"seat": rec.model_dump(mode="json"), "token": token}
    if method == "seat.approve":
        return store.approve_seat(str(args["seat_id"])).model_dump(mode="json")
    if method == "seat.kick":
        return store.kick_seat(str(args["seat_id"])).model_dump(mode="json")
    if method == "seat.revoke":
        return store.revoke_token(str(args["target"])).model_dump(mode="json")

    if method == "ruleset.list":
        return store.list_rulesets()
    if method == "ruleset.import":
        return store.import_ruleset(Path(str(args["path"])))
    if method == "ruleset.validate":
        return store.validate_ruleset(str(args["path"]))

    if method == "admin.rotate_token":
        return {"admin_token": store.rotate_admin_token()}

    if method == "mud.attach_info":
        return store.session_status().model_dump(mode="json")

    if method == "mud.command":
        eng = store.active_engine
        if eng is None:
            cid = str(args["campaign_id"]) if args.get("campaign_id") else None
            if cid is None:
                camps = store.list_campaigns()
                if not camps:
                    raise RuntimeError("No active campaign session and library is empty.")
                cid = camps[0].campaign_id
            store.start_session(cid)
            eng = store.active_engine
        assert eng is not None
        res = eng.execute_command(
            str(args.get("command", "look")),
            seat_id=seat_id,
            seat_role=seat_role,
        )
        store._persist_active_engine()
        return res.model_dump(mode="json")

    raise KeyError(f"Unknown RPC method '{method}'.")


class MeddahHeadlessServer:
    """Authoritative Python asyncio HTTP + WebSocket + UNIX-Socket daemon (`meddah serve`)."""

    def __init__(
        self,
        store: HeadlessLibraryStore,
        *,
        host: str = "127.0.0.1",
        port: int = 8765,
        admin_sock: Path | None = None,
        serve_web_client: bool = False,
        web_client_dir: Path | None = None,
    ) -> None:
        self.store = store
        self.host = host
        self.requested_port = port
        self.bound_port: int = port
        self.admin_sock = admin_sock
        self.serve_web_client = serve_web_client
        self.web_client_dir = web_client_dir
        self._tcp_server: asyncio.AbstractServer | None = None
        self._unix_server: asyncio.AbstractServer | None = None
        self._ws_clients: set[asyncio.StreamWriter] = set()
        self._shutdown_event = asyncio.Event()
        self.shutdown_checkpoint_written = False

    async def start(self) -> None:
        """Bind TCP listener and optional UNIX domain admin socket."""
        self.store.ensure_admin_token()
        self._shutdown_event.clear()

        async def _tcp_cb(r: asyncio.StreamReader, w: asyncio.StreamWriter) -> None:
            await self._handle_client(r, w, is_unix=False)

        self._tcp_server = await asyncio.start_server(_tcp_cb, self.host, self.requested_port)
        if self._tcp_server.sockets:
            sock_port = self._tcp_server.sockets[0].getsockname()[1]
            self.bound_port = int(sock_port)

        if self.admin_sock is not None:
            sock_path = Path(self.admin_sock)
            sock_path.parent.mkdir(parents=True, exist_ok=True)
            if sock_path.exists():
                sock_path.unlink()

            async def _unix_cb(r: asyncio.StreamReader, w: asyncio.StreamWriter) -> None:
                await self._handle_client(r, w, is_unix=True)

            self._unix_server = await asyncio.start_unix_server(_unix_cb, path=str(sock_path))

    async def shutdown(self) -> None:
        """Broadcast shutdown notice, write atomic checkpoint, and close listeners."""
        notice = json.dumps(
            {
                "type": "server_shutdown",
                "notice": "Meddah server shutting down gracefully; saving checkpoint.",
            }
        ).encode("utf-8")
        frame = _encode_ws_frame(notice, opcode=0x1, mask=False)
        for ws in list(self._ws_clients):
            try:
                ws.write(frame)
                ws.write(_encode_ws_frame(b"", opcode=0x8, mask=False))
                await ws.drain()
                ws.close()
            except Exception:
                pass
        self._ws_clients.clear()

        if self.store.active_engine is not None and not self.shutdown_checkpoint_written:
            self.store.checkpoint_session(label="shutdown_checkpoint")
            self.shutdown_checkpoint_written = True

        if self._tcp_server is not None:
            self._tcp_server.close()
            await self._tcp_server.wait_closed()
            self._tcp_server = None
        if self._unix_server is not None:
            self._unix_server.close()
            await self._unix_server.wait_closed()
            self._unix_server = None
        if self.admin_sock is not None and Path(self.admin_sock).exists():
            with contextlib.suppress(OSError):
                Path(self.admin_sock).unlink()
        self._shutdown_event.set()

    async def serve_forever(self) -> None:
        """Run server loop with SIGTERM/SIGINT graceful checkpoint handlers until shutdown."""
        if self._tcp_server is None:
            await self.start()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            with contextlib.suppress(NotImplementedError, RuntimeError):
                loop.add_signal_handler(sig, lambda: asyncio.create_task(self.shutdown()))
        await self._shutdown_event.wait()

    def _authenticate_tcp(
        self,
        headers: Mapping[str, str],
        query_token: str | None,
        *,
        allow_seat: bool,
    ) -> tuple[bool, str, SeatRole]:
        auth_hdr = headers.get("authorization", "")
        bearer = auth_hdr[7:].strip() if auth_hdr.lower().startswith("bearer ") else None
        token = bearer or query_token
        if self.store.verify_admin_token(token):
            return True, "seat_host", "gm"
        if allow_seat and token:
            seat = self.store.authenticate_seat_token(token)
            if seat is not None:
                role_map: dict[str, SeatRole] = {
                    "host": "host",
                    "gm": "gm",
                    "co_gm": "co_gm",
                    "host_player": "player",
                    "player": "player",
                    "spectator": "spectator",
                }
                return True, seat.seat_id, role_map.get(seat.role, "player")
        return False, "", "player"

    async def _send_http(
        self,
        writer: asyncio.StreamWriter,
        status_code: int,
        reason: str,
        body: bytes,
        *,
        content_type: str = "application/json",
    ) -> None:
        hdr = (
            f"HTTP/1.1 {status_code} {reason}\r\n"
            f"Content-Type: {content_type}\r\n"
            f"Content-Length: {len(body)}\r\n"
            "Connection: close\r\n\r\n"
        ).encode("ascii")
        writer.write(hdr + body)
        await writer.drain()

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        *,
        is_unix: bool,
    ) -> None:
        try:
            raw_hdr = await reader.readuntil(b"\r\n\r\n")
        except (asyncio.IncompleteReadError, asyncio.LimitOverrunError, OSError):
            writer.close()
            return

        hdr_text = raw_hdr.decode("utf-8", errors="replace")
        lines = hdr_text.split("\r\n")
        if not lines or " " not in lines[0]:
            await self._send_http(writer, 400, "Bad Request", b'{"error":"Malformed HTTP"}')
            writer.close()
            return

        req_parts = lines[0].split()
        method = req_parts[0].upper()
        target = req_parts[1] if len(req_parts) > 1 else "/"
        parsed_url = urllib.parse.urlsplit(target)
        path = parsed_url.path
        query = urllib.parse.parse_qs(parsed_url.query)
        q_token = query.get("token", [None])[0]

        headers: dict[str, str] = {}
        for ln in lines[1:]:
            if ":" in ln:
                k, v = ln.split(":", 1)
                headers[k.strip().lower()] = v.strip()

        if method == "GET" and path == "/api/health":
            payload = json.dumps(
                {
                    "status": "ok",
                    "version": "0.2.5",
                    "mode": self.store.server_mode,
                    "ai_provider": self.store.ai_provider,
                }
            ).encode("utf-8")
            await self._send_http(writer, 200, "OK", payload)
            writer.close()
            return

        if method == "GET" and path == "/api/ready":
            st = self.store.session_status()
            payload = json.dumps(
                {
                    "ready": True,
                    "active_campaign_id": st.active_campaign_id,
                    "ruleset_hash": st.ruleset_hash,
                }
            ).encode("utf-8")
            await self._send_http(writer, 200, "OK", payload)
            writer.close()
            return

        if method == "GET" and path == "/ws/mud":
            ws_key = headers.get("sec-websocket-key")
            if not ws_key or headers.get("upgrade", "").lower() != "websocket":
                await self._send_http(writer, 400, "Bad Request", b'{"error":"Expected WebSocket"}')
                writer.close()
                return
            if is_unix:
                authed, seat_id, seat_role = True, "seat_host", "gm"
            else:
                authed, seat_id, seat_role = self._authenticate_tcp(
                    headers, q_token, allow_seat=True
                )
            if not authed:
                await self._send_http(writer, 401, "Unauthorized", b'{"error":"Unauthorized"}')
                writer.close()
                return

            accept = _ws_accept_key(ws_key)
            handshake = (
                "HTTP/1.1 101 Switching Protocols\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                f"Sec-WebSocket-Accept: {accept}\r\n\r\n"
            ).encode("ascii")
            writer.write(handshake)
            await writer.drain()
            await self._serve_ws_loop(reader, writer, seat_id=seat_id, seat_role=seat_role)
            return

        if method == "POST" and path == "/api/rpc":
            content_len = int(headers.get("content-length", "0"))
            body_bytes = await reader.readexactly(content_len) if content_len > 0 else b"{}"
            try:
                rpc_req = json.loads(body_bytes.decode("utf-8"))
            except json.JSONDecodeError:
                await self._send_http(writer, 400, "Bad Request", b'{"error":"Invalid JSON"}')
                writer.close()
                return

            rpc_method = str(rpc_req.get("method", ""))
            allow_seat = rpc_method in {"mud.command", "mud.attach_info"}
            if is_unix:
                authed, seat_id, seat_role = True, "seat_host", "gm"
            else:
                authed, seat_id, seat_role = self._authenticate_tcp(
                    headers, q_token, allow_seat=allow_seat
                )
            if not authed:
                await self._send_http(writer, 401, "Unauthorized", b'{"error":"Unauthorized"}')
                writer.close()
                return

            rpc_params = rpc_req.get("params")
            try:
                result = dispatch_rpc_method(
                    self.store,
                    rpc_method,
                    rpc_params if isinstance(rpc_params, Mapping) else None,
                    seat_id=seat_id,
                    seat_role=seat_role,
                )
                out = json.dumps({"ok": True, "result": result}).encode("utf-8")
                await self._send_http(writer, 200, "OK", out)
            except (KeyError, ValueError, RuntimeError, PermissionError, FileNotFoundError) as exc:
                err_out = json.dumps({"ok": False, "error": str(exc)}).encode("utf-8")
                await self._send_http(writer, 400, "Bad Request", err_out)
            writer.close()
            return

        if method == "GET" and self.serve_web_client:
            html = (
                b"<!doctype html><html><head><title>Meddah Headless Server</title></head>"
                b"<body><h1>Meddah Headless Server v0.2.5</h1>"
                b"<p>Unified Browser Web Client bundle attaches in Phase 6; use `meddah attach` "
                b"or WebSocket <code>/ws/mud</code> now.</p></body></html>"
            )
            await self._send_http(writer, 200, "OK", html, content_type="text/html; charset=utf-8")
            writer.close()
            return

        await self._send_http(writer, 404, "Not Found", b'{"error":"Not Found"}')
        writer.close()

    async def _serve_ws_loop(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        *,
        seat_id: str,
        seat_role: SeatRole,
    ) -> None:
        self._ws_clients.add(writer)
        try:
            while True:
                frame = await _read_ws_frame_async(reader)
                if frame is None:
                    break
                opcode, payload = frame
                if opcode == 0x8:
                    writer.write(_encode_ws_frame(b"", opcode=0x8, mask=False))
                    await writer.drain()
                    break
                if opcode == 0x9:
                    writer.write(_encode_ws_frame(payload, opcode=0xA, mask=False))
                    await writer.drain()
                    continue
                if opcode != 0x1:
                    continue

                msg = json.loads(payload.decode("utf-8"))
                cmd_text = str(msg.get("command", "look"))
                cid = str(msg["campaign_id"]) if msg.get("campaign_id") else None
                try:
                    res = dispatch_rpc_method(
                        self.store,
                        "mud.command",
                        {"command": cmd_text, "campaign_id": cid},
                        seat_id=seat_id,
                        seat_role=seat_role,
                    )
                    out = json.dumps({"type": "mud_turn", "result": res}).encode("utf-8")
                except (KeyError, ValueError, RuntimeError, PermissionError) as exc:
                    out = json.dumps({"type": "error", "error": str(exc)}).encode("utf-8")
                writer.write(_encode_ws_frame(out, opcode=0x1, mask=False))
                await writer.drain()
        except (OSError, json.JSONDecodeError):
            pass
        finally:
            self._ws_clients.discard(writer)
            with contextlib.suppress(OSError):
                writer.close()


class _UnixHttpConnection(http.client.HTTPConnection):
    def __init__(self, socket_path: str, timeout: float = 10.0) -> None:
        super().__init__("localhost", timeout=timeout)
        self.socket_path = socket_path

    def connect(self) -> None:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        sock.connect(self.socket_path)
        self.sock = sock


class HeadlessRpcClient:
    """Dispatches admin or MUD RPC calls to local UNIX socket, HTTP server, or local store."""

    def __init__(
        self,
        *,
        store: HeadlessLibraryStore | None = None,
        server_url: str | None = None,
        admin_sock: Path | None = None,
        token: str | None = None,
    ) -> None:
        self.store = store
        self.server_url = server_url.rstrip("/") if server_url else None
        self.admin_sock = admin_sock
        self.token = token

    def call(self, method: str, params: Mapping[str, object] | None = None) -> object:
        """Execute RPC call across configured transport."""
        body = json.dumps({"method": method, "params": dict(params or {})}).encode("utf-8")
        if self.admin_sock is not None and Path(self.admin_sock).exists():
            conn = _UnixHttpConnection(str(self.admin_sock))
            conn.request(
                "POST", "/api/rpc", body=body, headers={"Content-Type": "application/json"}
            )
            resp = conn.getresponse()
            raw = resp.read().decode("utf-8")
            conn.close()
            parsed = json.loads(raw)
            if not parsed.get("ok"):
                raise RuntimeError(str(parsed.get("error", f"HTTP {resp.status}")))
            return parsed["result"]

        if self.server_url is not None:
            headers = {"Content-Type": "application/json"}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            req = urllib.request.Request(
                f"{self.server_url}/api/rpc",
                data=body,
                headers=headers,
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=15.0) as resp:
                    parsed = json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                err_body = exc.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"Server error {exc.code}: {err_body}") from exc
            if not parsed.get("ok"):
                raise RuntimeError(str(parsed.get("error", "RPC error")))
            return parsed["result"]

        if self.store is not None:
            return dispatch_rpc_method(self.store, method, params)

        raise RuntimeError("No HeadlessRpcClient transport configured.")


class WsMudClient:
    """Zero-dependency RFC 6455 WebSocket client for `meddah attach --server ...`."""

    def __init__(
        self,
        server_url: str,
        *,
        token: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.server_url = server_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self._sock: socket.socket | None = None

    def connect(self) -> None:
        """Open TCP connection and complete RFC 6455 HTTP 101 WebSocket handshake."""
        parsed = urllib.parse.urlsplit(self.server_url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or (443 if parsed.scheme in {"https", "wss"} else 80)
        sock = socket.create_connection((host, port), timeout=self.timeout)
        ws_key = base64.b64encode(secrets.token_bytes(16)).decode("ascii")
        lines = [
            "GET /ws/mud HTTP/1.1",
            f"Host: {host}:{port}",
            "Upgrade: websocket",
            "Connection: Upgrade",
            f"Sec-WebSocket-Key: {ws_key}",
            "Sec-WebSocket-Version: 13",
        ]
        if self.token:
            lines.append(f"Authorization: Bearer {self.token}")
        req = ("\r\n".join(lines) + "\r\n\r\n").encode("ascii")
        sock.sendall(req)

        buf = bytearray()
        while b"\r\n\r\n" not in buf:
            chunk = sock.recv(4096)
            if not chunk:
                sock.close()
                raise ConnectionError("WebSocket handshake closed before completion.")
            buf.extend(chunk)
        status_line = buf.decode("utf-8", errors="replace").split("\r\n", 1)[0]
        if "101" not in status_line:
            sock.close()
            raise PermissionError(f"WebSocket handshake failed: {status_line}")
        self._sock = sock

    def send_command(self, command: str, *, campaign_id: str | None = None) -> MudTurnResult:
        """Send one MUD command over WebSocket and parse the returned MudTurnResult."""
        if self._sock is None:
            self.connect()
        assert self._sock is not None
        payload = json.dumps({"command": command, "campaign_id": campaign_id}).encode("utf-8")
        self._sock.sendall(_encode_ws_frame(payload, opcode=0x1, mask=True))
        while True:
            frame = _read_ws_frame_sync(self._sock)
            if frame is None:
                raise ConnectionError("WebSocket stream closed unexpectedly.")
            opcode, data = frame
            if opcode == 0x8:
                raise ConnectionError("WebSocket closed by server.")
            if opcode == 0x9:
                self._sock.sendall(_encode_ws_frame(data, opcode=0xA, mask=True))
                continue
            if opcode == 0x1:
                parsed = json.loads(data.decode("utf-8"))
                if parsed.get("type") == "error":
                    raise RuntimeError(str(parsed.get("error", "Remote command failed")))
                return MudTurnResult.model_validate(cast(dict[str, object], parsed["result"]))

    def close(self) -> None:
        """Send clean WebSocket close frame and close underlying socket."""
        if self._sock is not None:
            with contextlib.suppress(OSError):
                self._sock.sendall(_encode_ws_frame(b"", opcode=0x8, mask=True))
            with contextlib.suppress(OSError):
                self._sock.close()
            self._sock = None
