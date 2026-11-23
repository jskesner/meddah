# 0105. Spectator Mode

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Grill-Me Resolution #55 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Spectator Mode**.

## Decision
A read-only seat role. The host chooses the audience view: Public (shared MUD log, public map state, shared handouts, public dice results) or Party (adds one chosen party's perspective and fog-of-war). Never GM-only data, hidden rolls, secrets, other split parties' private scenes, or character sheets (unless the host enables sheets). Optional configurable delay (e.g. 0–120s) for streaming without spoilers. **No spectator chat.** Joined via a spectator invite link, subject to a host-set cap, using the browser client in read-only mode. Filtering is server-side with the same role-based view filter as players.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
