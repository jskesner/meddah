# 0031. Modular Puzzle & Trap Generator, Dynamic Topology & Catastrophic Wavefronts

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Architectural Decision #31 (`docs/design/system_design_specification.md`)

## Context & Problem Statement
Architectural design constraint and domain resolution for **Modular Puzzle & Trap Generator, Dynamic Topology & Catastrophic Wavefronts** in Meddah: The Universal Story Engine.

## Decision
**100% Ruleset-Grounded Contraption, Map Mutation & Multi-Phase Environmental Engine**: **(1) Zero Forced Outcomes, Math, or Conditions** (no puzzle, trap, flood, gas cloud, or terrain change ever assumes hardcoded damage types, saving throws, movement multipliers, or status conditions like "Prone" or "Difficult Terrain"—every stage strictly binds to `ResolutionMechanics`, `Actions`, `Conditions`, and `TerrainRules` defined in the active `.rpgrules` schema, or executes purely as a spatial/narrative state change if the ruleset defines no mechanical modifier for that terrain); **(2) Modular Building Blocks** (`Sensors -> Logic Gates -> Payloads`); **(3) Dynamic Dungeon & Local Map Layout Mutation** (rotating chambers, collapsing corridors, extending bridges, sliding walls, opening `Z-1` floor pits); **(4) Progressive & Multi-Phase Environmental Sequences** (*Stage 1 [Acute Surge]* $\rightarrow$ *Stage 2 [Peak]* $\rightarrow$ *Stage 3 [Persistent Residual Aftermath]* like a Dam Collapse leaving persistent ankle-deep water, evaluated 100% through the active ruleset's defined mechanics); and **(5) Visual Contraption Studio & Spoiler-Free Solo Generator**.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Enforced by phase DoD suites (`pytest -m zero_ai`, `tools/lint_agnosticism.py`, `tools/lint_modularity.py`, and `import-linter`) as implementation lands.
