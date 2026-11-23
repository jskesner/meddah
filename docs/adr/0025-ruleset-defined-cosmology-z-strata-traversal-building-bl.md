# 0025. Ruleset-Defined Cosmology, Z-Strata & Traversal Building Blocks

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Architectural Decision #25 (`docs/design/system_design_specification.md`)

## Context & Problem Statement
Architectural design constraint and domain resolution for **Ruleset-Defined Cosmology, Z-Strata & Traversal Building Blocks** in Meddah: The Universal Story Engine.

## Decision
**Zero-Assumption Cosmology & Topology Building Blocks**: **No world scales, Z-strata, planes, or vehicle/hyperspace layers are ever assumed by default.** Instead, **World Scales**, **Z-Strata Layers**, **Dimensional Phases (Independent, Coterminous, or Transit/Hyperspace)**, **Mobile Vessel Archetypes**, and **Traversal Precondition Rules** are modular **Ruleset Building Blocks** actively extracted by the Ruleset Ingestor (or manually added/edited in the Ruleset Studio). A grounded single-level ruleset only shows a simple flat map, whereas a ruleset defining Underdark strata, Astral Planes, Cyberspace, or Hyperspace dynamically unlocks those exact UI controls and mechanics.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Enforced by phase DoD suites (`pytest -m zero_ai`, `tools/lint_agnosticism.py`, `tools/lint_modularity.py`, and `import-linter`) as implementation lands.
