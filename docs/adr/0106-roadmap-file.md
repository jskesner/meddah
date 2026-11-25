# 0106. Roadmap File

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Design Resolution #56 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Roadmap File**.

## Decision
A self-contained `ROADMAP.md` at the repo root is the single source of truth for planned work (not GitHub Projects). It lists all phases (14 + 2.5, with contiguous MVP Phases 1–6 + 2.5 and Post-MVP Phases 7–14), each with status (`Planned / In Progress / Done / Deferred`), MVP flag, deliverables checklist, and links to ADRs and spec sections, plus a "Deferred / Ideas" section. A machine-readable front-matter table is validated in CI by `tools/roadmap.py` (valid statuses, every Done phase has a tag and DoD checkbox, links resolve). GitHub Issues are used ONLY for bugs and user-reported problems (bug template, plus a lightweight feature-suggestion template that the maintainer triages into the roadmap file); issues may reference roadmap IDs but never replace them.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
