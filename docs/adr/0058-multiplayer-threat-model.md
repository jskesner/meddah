# 0058. Multiplayer Threat Model

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Design Resolution #8 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Multiplayer Threat Model**.

## Decision
Host-authoritative with server-side validation. Guests send only intents, never state. The server filters fog-of-war, hidden rolls, and GM-only data before transmission, and Tunnel/Invite Codes require a per-session token. Trust model is friends-and-family (not hostile public play), but secrets are never sent to clients.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
