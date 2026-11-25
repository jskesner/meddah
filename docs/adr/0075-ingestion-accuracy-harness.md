# 0075. Ingestion Accuracy Harness (Phase 2 Dual-Track Gate)

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Design Resolution #25 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Ingestion Accuracy Harness (Phase 2 Dual-Track Gate)**.

## Decision
A small corpus of open-licensed rulebooks (e.g. SRD 5.1, Cairn, Ironsworn, FATE Core, BRP SRD) with hand-authored gold `.rpgrules`. Evaluated on two tracks: **Track 1 (`Tier A` Deterministic Gate)** requires 100% pass rate on structured YAML/JSON/Markdown/CSV imports and deterministic regex/table probes with `AI_PROVIDER=none`; **Track 2 (`Tier B` Local 7–14B LLM Gate)** evaluates unstructured rulebook extraction on our reference 7–14B local model via Ollama (metrics: per-domain precision/recall of extracted blocks, formula-correctness on sampled rolls, and zero falsely invented domains, with $\ge 90\%$ core mechanics correctness).

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
