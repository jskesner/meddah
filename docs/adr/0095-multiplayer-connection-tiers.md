# 0095. Multiplayer Connection Tiers (no public server required)

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Grill-Me Resolution #45 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Multiplayer Connection Tiers (no public server required)**.

## Decision
The host's backend serves the browser guest client itself. (1) LAN/direct: guests open `https://host-ip:port` (self-signed or locally trusted cert, with clear instructions). (2) One-click tunnel (e.g. Cloudflare Tunnel) provides valid public HTTPS with no port forwarding. (3) VPN overlays (Tailscale/ZeroTier) are documented, not built in. (4) WebRTC peer-to-peer is post-MVP. The invite is a short code plus a link carrying a per-session token; a host waiting room approves each guest; the Electron client can join by the same link.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
