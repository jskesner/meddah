# 0071. Onboarding / First-Run Wizard

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Grill-Me Resolution #21 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Onboarding / First-Run Wizard**.

## Decision
Skippable steps: (1) detect and test-ping local providers (Ollama, llama.cpp, ComfyUI, Kokoro/Piper); (2) recommend models by detected VRAM with one-click Ollama pull; (3) optional cloud API keys (keychain); (4) pick a showcase ruleset; (5) a 10-minute guided tutorial scenario (MUD commands, roll prompts, VTT toggle). Reopenable from Settings. "Play without AI" (zero-LLM mode) is a first-class choice.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
