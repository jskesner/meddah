# 0018. Customizable Visual Theme Engine

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Architectural Decision #18 (`docs/design/system_design_specification.md`)

## Context & Problem Statement
Architectural design constraint and domain resolution for **Customizable Visual Theme Engine** in Meddah: The Universal Story Engine.

## Decision
**Token-Driven Theme Architecture + 6 Pre-Made Genre Presets + Live Theme Editor**: Full GUI theming (colors, typography, panel borders/surfaces, CRT/parchment/glass effects, MUD syntax highlighting, and VTT grid aesthetics) with 6 built-in themes (*Obsidian Grimdark*, *Arcane Grimoire / Parchment*, *Phosphor CRT MUD*, *Cyberpunk Neon HUD*, *Astral Sci-Fi Glass*, and *Clean Daylight Tabletop*), custom user theme creation/export (`.rpgtheme`), and optional per-ruleset/per-world automatic theme binding.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Enforced by phase DoD suites (`pytest -m zero_ai`, `tools/lint_agnosticism.py`, `tools/lint_modularity.py`, and `import-linter`) as implementation lands.
