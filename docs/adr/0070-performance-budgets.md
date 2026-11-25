# 0070. Performance Budgets (CI-tested)

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Design Resolution #20 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Performance Budgets (CI-tested)**.

## Decision
Deterministic command round-trip <5ms; state diff to clients <50ms; 60fps on a 100x100 tactical map with 50 tokens; 30fps on the multi-scale canvas; cold start <10s excluding LLM load; backend memory <1.5GB with no model loaded (LLM runs out-of-process); replay of 100k events <5s (checkpoints bound the typical case). Documented reference machine: 8-core CPU, 16GB RAM, 8GB-VRAM GPU.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
