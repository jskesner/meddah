# 0062. Media & Secrets Management (Desktop Keychain + Layered Headless Secret Resolver)

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Grill-Me Resolution #12 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Media & Secrets Management (Desktop Keychain + Layered Headless Secret Resolver)**.

## Decision
Content-addressed local media cache in the campaign folder. Media is generated only when a provider is configured, with a per-session size/cost cap and a visible "generating" placeholder. On Desktop, provider API keys live in the OS keychain; on **Headless Linux / Docker** (where no desktop OS keyring exists), the **Layered Headless Secret Resolver** loads secrets in priority order from: (1) Docker Secrets / file-mounted paths (`*_FILE` env vars such as `/run/secrets/openai_api_key`), (2) standard environment variables (`.env` / `OPENAI_API_KEY`), or (3) an optional age/Fernet-encrypted `/data/config/secrets.enc` vault unlocked via `MEDDAH_MASTER_KEY`—and strictly never stores secrets in `.rpgcampaign` files or SQLite event logs. Campaign export bundles media optionally. The campaign works fully with no media providers.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
