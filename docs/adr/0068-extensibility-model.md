# 0068. Extensibility Model

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Design Resolution #18 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Extensibility Model**.

## Decision
Post-MVP, declarative-first. Content extensions (blocks, tilesets, themes, prompts, tables) are code-free packages. Behavioral extensions (custom LLM/image/TTS providers, importers) use a versioned Python provider interface, loaded only from a user-approved folder with a permissions manifest. The provider interfaces built in Phases 4 and 5 are written to this contract from the start.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
