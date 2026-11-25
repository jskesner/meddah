# 0085. Wire Protocol Versioning & Handshake

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Design Resolution #35 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Wire Protocol Versioning & Handshake**.

## Decision
Each WebSocket session starts with a handshake exchanging `protocol_version` (major.minor), engine version, and ruleset/world hashes. Major mismatch is refused with a clear "please update" message; minor mismatch is allowed (additive changes, unknown fields ignored). Typed JSON-RPC envelopes with schemas generated from Pydantic. Guests must hold the host's pinned ruleset hash; the host streams the package on join if missing, after guest approval. Hosts send only role-visible state.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
