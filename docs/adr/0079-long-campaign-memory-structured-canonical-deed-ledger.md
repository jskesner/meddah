# 0079. Long-Campaign Memory & Structured Canonical Deed Ledger

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Design Resolution #29 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Long-Campaign Memory & Structured Canonical Deed Ledger**.

## Decision
(1) Canonical facts (names, relationships, quest state, inventory, faction standing) plus the **Structured Canonical Deed Ledger (`canonical_deed_ledger.py` `DeedFact` records)** live as structured event-store state, never summarized away, and are queried deterministically by ID/tags so `Tier A (Zero-AI Mode)` NPCs, companions, and chronicles remember past deeds across 50+ sessions with `0` LLM calls—and so campaigns can hot-swap freely between `Tier A` and `Tier B/C`. (2) Episodic scene summaries written at scene end with importance scores and decay (LLM-summarized in `Tier B/C` or deterministic digest in `Tier A`). (3) Rolling hierarchical summary (scene → session → arc) keeps the 4k–8k `Tier B` prompt bounded. (4) Facts the LLM asserts that conflict with canonical state are rejected by the tool-call validator. (5) A "Campaign Memory" viewer lets players pin, edit, or delete memories. Prompt budgets per section are fixed (starting point: 40% scene, 25% canonical facts & deeds, 20% memory, 15% rules), tuned for `Tier B` (4k–8k context).

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
