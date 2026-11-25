# 0097. Guest Identity & Seats

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Design Resolution #47 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Guest Identity & Seats**.

## Decision
Per-seat invite links persisted in the browser (localStorage token) let guests rejoin the same seat after refresh or disconnect, with no account. The host may optionally "remember" a guest and bind a seat to a stored device token across sessions. Invites expire (default 24h or on session end), can be revoked, and can be single-use or multi-use. Roles are per seat: `Player`, `Host-as-Player` (admin controls + player spoiler-shielding for AI-GMed / Solo-Oracle co-op), `Spectator`, `Co-GM`, and `Host-as-GM`. The host can kick or ban a device token. No central identity service exists.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
