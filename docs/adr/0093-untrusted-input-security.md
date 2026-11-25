# 0093. Untrusted-Input Security

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Design Resolution #43 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Untrusted-Input Security**.

## Decision
(1) Formula/AST evaluation uses a custom parser with no `eval`/`exec`, a function whitelist, and hard limits on depth, node count, loop iterations, and wall-time. (2) Package import rejects path traversal (zip-slip), absolute paths, symlinks, and zip bombs (entry count, per-file and total uncompressed size, compression-ratio cap) and validates manifest/schema before extracting. (3) URL ingestion blocks private/loopback addresses (SSRF) and limits redirects, response size, and content types, with an optional domain allowlist. (4) PDF/HTML parsing runs in a subprocess with size/time limits. (5) Extension providers and WebSocket messages are schema-validated with size and rate limits. (6) Ruleset and AI text is escaped before rendering; the Electron renderer uses `contextIsolation` on, `nodeIntegration` off, and a strict CSP.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
