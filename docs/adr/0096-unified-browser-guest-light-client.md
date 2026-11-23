# 0096. Unified Browser Guest / Light Client (Spectator, Player, Co-GM, Host-as-Player & Host-as-GM Modes)

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Grill-Me Resolution #46 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Unified Browser Guest / Light Client (Spectator, Player, Co-GM, Host-as-Player & Host-as-GM Modes)**.

## Decision
One single lightweight web build target of the shared React components: MUD terminal, character sheet, capabilities deck, roll/reaction prompts, handouts, journal, and a read-only or lightweight VTT view. Capabilities unlock along two orthogonal axes: **(A) In-Game Seat Role (`spectator | player | host_player | co_gm | gm`)** and **(B) Server Admin Privilege (`is_server_admin: bool`, via `MEDDAH_ADMIN_TOKEN` or Host link)**. When a Host/Admin wants to **play as a Player Character in a multiplayer game while the AI GM (`Tier B/C`) or Deterministic GM Director / Solo Oracle (`Tier A`) runs the game**, they select **`Host-as-Player` Mode (`seat_role: "host_player"`)**: the server keeps the **Server & Session Admin Drawer** and **Shared Solo Oracle Drawer** unlocked for them while enforcing **strict Player-Level Fog-of-War & Spoiler Shielding** (hiding unrevealed map areas, secret doors, trap icons, and hidden NPC plots, and locking the Live GM Dock behind a spoiler confirmation guard). Conversely, selecting **`Host-as-GM` Mode (`seat_role: "gm"`)** unlocks both the Server Admin Drawer and the omniscient Live GM Dock. Heavy authoring Studios (Visual Ruleset Studio, Map/Tileset Import Studio, World Builder) stay in the Electron Desktop App—which can either run its own local sidecar OR connect directly to a remote Headless Server (`https://...` + `MEDDAH_ADMIN_TOKEN`) as a remote Studio workstation. Served by the host backend as static files (no separate web server needed). **Mobile phone support is explicitly off the roadmap for now.**

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
