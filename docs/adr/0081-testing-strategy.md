# 0081. Testing Strategy

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Design Resolution #31 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Testing Strategy**.

## Decision
Unit and property-based tests (Hypothesis) for the VM, dice, AST evaluator, and parsers, plus a malformed-ruleset fuzzer; golden-file scenario tests; event-store tests (replay determinism, migration, crash injection); a multiplayer integration harness with scripted headless clients (latency, disconnects, concurrent actions); a scripted mock LLM provider for deterministic CI; UI component tests, Playwright E2E against the Electron app, and visual-regression snapshots for the VTT canvas. Coverage is tracked per subsystem, with the VM core held to a higher bar. **Real-LLM evals are NOT run on a schedule** (hobby-project scope): they run only when a phase gate requires them (Phase 2 ingestion harness, Phase 4 AI GM acceptance scenario) or when manually triggered after prompt/model changes.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
