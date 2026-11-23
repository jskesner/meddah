# 0107. Sample Ruleset Sourcing

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Grill-Me Resolution #57 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Sample Ruleset Sourcing**.

## Decision
Derive where it helps, original where it doesn't. The d20 fantasy and 2d6 narrative rulesets are adapted from open-licensed SRDs (e.g. SRD 5.1 under CC-BY 4.0, and an open PbtA-style SRD) with attribution, also providing realistic gold data for the Phase 2 ingestion harness. The d100, dice-pool, step/symbol-dice, resource-wager/card, and rules-light fixtures are original and intentionally small (core resolution loop, one sample character, one encounter, two golden scenarios each). The 3 showcase rulesets get fuller content and sample modules; the other 4 are minimal conformance fixtures. Attribution is recorded in `assets/PROVENANCE.md` and the package manifest.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
