# 0090. Branching, Commits & Releases

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Design Resolution #40 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Branching, Commits & Releases**.

## Decision
Trunk-based development on `main` with short-lived branches and small PRs (self-review checklist for solo work; CI must be green). Conventional Commits enforced by a commit-msg hook. SemVer with `0.x` until formats stabilize. Package formats and the wire protocol are versioned and migrated from the first tagged release; internal Python APIs are unstable until 1.0. `CHANGELOG.md` generated at each tag. Each phase ends with a tagged milestone release (`v0.N`) and a demo script.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
