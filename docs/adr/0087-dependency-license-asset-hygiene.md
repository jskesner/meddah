# 0087. Dependency, License & Asset Hygiene

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Design Resolution #37 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Dependency, License & Asset Hygiene**.

## Decision
Lockfiles for both ecosystems; grouped monthly update PRs (Dependabot/Renovate-style); `pip-audit` and `pnpm audit` plus a license checker with an allowlist (MIT/BSD/Apache/MPL/ISC; GPL/AGPL/unknown require an ADR). Project license MIT or Apache-2.0 (chosen at repo creation). `THIRD_PARTY_NOTICES.md` generated from lockfiles; `assets/PROVENANCE.md` records source and license of every bundled asset, sample ruleset, font, and sound. Model weights are never bundled.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
