# 0110. Optional Headless / Server-Only Installation, CLI Server Management, Remote Desktop Sync & Official NVIDIA/AMD ROCm Docker Deployment

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Design Resolution #60 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Optional Headless / Server-Only Installation, CLI Server Management, Remote Desktop Sync & Official NVIDIA/AMD ROCm Docker Deployment**.

## Decision
- **Standalone Python Server Install (Zero Electron/Desktop GUI Required)**: Users can install only the authoritative Python backend (`uv tool install ./backend` or `pipx install ./backend`) on a headless Linux box, home server, NAS, or VPS without installing Electron or any desktop GUI libraries.
   - **Standalone Python Server Install (Zero Electron/Desktop GUI Required)**: Users can install only the authoritative Python backend (`uv tool install ./backend` or `pipx install ./backend`) on a headless Linux box, home server, NAS, or VPS without installing Electron or any desktop GUI libraries.
   - **Dual Local Socket + `MEDDAH_ADMIN_TOKEN` Authentication**: Local CLI commands on the server host (`meddah seat approve`, `meddah campaign list`) communicate over a local UNIX domain socket (`/run/meddah/admin.sock` or loopback admin port) with zero friction, while remote CLI (`--server https://...`) and Browser Light Client / Remote Desktop Host logins authenticate via a high-entropy `MEDDAH_ADMIN_TOKEN` (printed on first boot, settable via env var, or rotated via `meddah admin rotate-token`).
   - **Multi-Campaign Library + 1 Active Live Session (Hot-Swappable)**: A headless server manages a persistent library of multiple `.rpgcampaign` folders on disk and runs 1 active live session in memory at a time—allowing the Host/Admin to cleanly switch active campaigns (`meddah session switch <campaign_id>` or via the Browser Host dashboard) without restarting the server or container.
   - **Full CLI Server, Campaign, Service & GPU Administration (`meddah`)**:
     - `meddah serve [--host 0.0.0.0] [--port 8420] [--campaign <id>] [--ai-provider none|ollama|...] [--serve-web-client]`
     - `meddah campaign list | create | import | export | info | delete`
     - `meddah session status | start | switch <campaign_id> | wrap-up | end | checkpoint | rewind <event_id> | backup`
     - `meddah seat list | invite --role host|gm|player|spectator | approve <id> | kick <id> | revoke <token>`
     - `meddah ruleset list | import <path> | validate <path>`
     - `meddah service install-systemd [--user]` (generates a hardened `meddah.service` systemd unit with graceful `SIGTERM` checkpointing)
     - `meddah gpu-check [--setup-rocm]` (detects NVIDIA vs. AMD GPUs, checks ROCm `/dev/kfd` & `/dev/dri` device nodes, `video`/`render` group permissions, recommends `HSA_OVERRIDE_GFX_VERSION` for consumer Radeon GPUs if needed, and prints or runs host setup commands)
     - `meddah attach [--campaign <id>]` (interactive terminal MUD client for solo play or live GM administration over SSH).
   - **Unified Browser Guest / Light Client + Remote Desktop App Workstation Mode**: Building directly on Item 46's Browser Guest Client, connecting to `meddah serve --serve-web-client` with a Host/GM token unlocks Host & Live GM Dock drawers right in the browser, while users who also have the Electron Desktop App can connect it directly to a remote Headless Server (`https://...` + `MEDDAH_ADMIN_TOKEN`) to use the heavy Visual Ruleset & Map/Tileset Studios and sync packages over the API.
   - **Headless Secrets, Graceful `SIGTERM` Checkpointing & Pure-Python PDF Fallback**: Uses the Layered Headless Secret Resolver (`*_FILE` Docker secrets $\rightarrow$ env vars $\rightarrow$ encrypted `/data/config/secrets.enc`), traps `SIGTERM`/`SIGINT` to flush SQLite WAL and write an atomic shutdown checkpoint before notifying WebSocket clients, exposes `/api/health` and `/api/ready`, and uses a pure-Python PDF renderer (`WeasyPrint` / `ReportLab` / `fpdf2`) for PDF character sheets and session reports when Chromium is absent.
   - **Official Lean Docker Image & Multi-Vendor GPU Compose Profiles (`docker/Dockerfile.server` & `docker/docker-compose.server.yml`)**:
     - Lean base `meddah-server` image (`~150–250MB`: `python:3.12-slim` + `uv` backend + static Browser Guest/Light Client + 3 Showcase Rulesets + deterministic OpenCV/RapidOCR/PyMuPDF parsers, `0` bundled AI weights, non-root `meddah` user, `/data` volume).
     - `docker/docker-compose.server.yml` includes explicit one-flag profiles for every hardware setup:
       1. *Default (No profile flag)*: Pure `Tier A` (`meddah-server` only, starts in seconds).
       2. `--profile ollama-nvidia`: `ollama/ollama:latest` with NVIDIA Container Toolkit `deploy.resources.reservations.devices: [capabilities: [gpu]]`.
       3. `--profile ollama-amd`: `ollama/ollama:rocm` with `/dev/kfd` and `/dev/dri` device pass-through, `video`/`render` group bindings, and configurable `HSA_OVERRIDE_GFX_VERSION` / `ROCR_VISIBLE_DEVICES` environment pass-through (backed by `tools/setup_gpu_host.sh` and `meddah gpu-check` to guide or trigger host ROCm kernel driver / container setup).
       4. `--profile ollama-vulkan`: Universal Vulkan GPU fallback for Intel Arc / integrated / older GPUs.
       5. `--profile ollama-cpu`: CPU-only `Tier B-Lite` profile.
       6. `--profile piper-tts` and `--profile tunnel` (Cloudflare Tunnel).

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
