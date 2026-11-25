# 0078. AI GM Evaluation (Phase 4 Dual-Track Gate)

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Design Resolution #28 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **AI GM Evaluation (Phase 4 Dual-Track Gate)**.

## Decision
Evaluated on two tracks: **Track 1 (`Tier A` Deterministic Gate)** runs the 30-minute scripted d20 fantasy scenario end-to-end with `AI_PROVIDER=none` in every CI run; **Track 2 (`Tier B` Local 7–14B LLM Gate)** runs the same scripted scenario (seeded dice, pinned **7–14B local model via Ollama**) scored on rules fidelity (deterministic: `0` illegal tool calls, `0` state contradictions), narrative coherence/tone (1–5 rubric), pacing, and hint/mercy behavior. Both the AI GM under test and the rubric evaluator run locally on `Tier B` (`Ollama` 7–14B) by default (with an optional dev-only override if a developer ever wants to compare against another model). Real-LLM evals run on demand and at Phase 2 / Phase 4 gates (see item 31), never on a recurring CI schedule.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
