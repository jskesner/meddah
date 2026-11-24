# 0020. Content Safety, Trigger Boundaries & Visual Accessibility

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Architectural Decision #20 (`docs/design/system_design_specification.md`)

## Context & Problem Statement
Architectural design constraint and domain resolution for **Content Safety, Trigger Boundaries & Visual Accessibility** in Meddah: The Universal Story Engine.

## Decision
**First-Class Safety & Accessibility Suite**: **(1) Configurable Content Rating** (`E/Family`, `T/PG-13`, `M/Mature`, `Unrestricted/Custom` across Violence, Horror, Language, Romance, and Dark Themes), **(2) Tabletop Lines & Veils + Live X-Card / Rewind System** (anonymous multiplayer union of player triggers into Hard Boundaries/"Lines" and Fade-to-Black/"Veils" injected into AI GM/NPC/Image guardrails, plus one-click Pause/Rewrite), and **(3) Comprehensive Visual Impairment Aids** (Colorblind palettes + non-color pattern/icon encoding on VTT & MUD badges, OpenDyslexic & hyper-legible typography, 100%–200% UI/text scaling, WCAG 2.2 AA-verified (AAA where feasible) High-Contrast & Reduced Motion modes, and full ARIA Live Region screen-reader narration including keyboard-navigable VTT grid readout).

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Enforced by phase DoD suites (`pytest -m zero_ai`, `tools/lint_agnosticism.py`, `tools/lint_modularity.py`, and `import-linter`) as implementation lands.
