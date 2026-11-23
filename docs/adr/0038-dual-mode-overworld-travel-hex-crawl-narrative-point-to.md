# 0038. Dual-Mode Overworld Travel: Hex-Crawl & Narrative Point-to-Point

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Architectural Decision #38 (`docs/design/system_design_specification.md`)

## Context & Problem Statement
Architectural design constraint and domain resolution for **Dual-Mode Overworld Travel: Hex-Crawl & Narrative Point-to-Point** in Meddah: The Universal Story Engine.

## Decision
**Unified Hex-Crawl & Point-to-Point Journey Engine (`overworld_travel.py` & `overworld_map/`)**: **(1) Mode 1 — Regional / Sector Hex-Crawl Exploration** (interactive hex grid with **Explicit Border Hexes & Frontier Crossings to Neighboring Regions** preserving coordinate continuity across borders, 3-state Hex Fog-of-War [`Uncharted`, `Vantage-Revealed`, `Surveyed`], ruleset travel-watch movement costs by terrain/weather/vehicle, **Party Travel Roles** [*Navigator, Scout, Forager, Quartermaster, Lookout*], and per-hex Navigation/Discovery/Encounter rolls); **(2) Mode 2 — Narrative Point-to-Point Journey Sequencer** (plots multi-leg travel between known POIs/towns/regions with an animated route progress marker, scheduled **Roadside Camp & Rest Stops** [Section 1.13], **Mid-Journey Companion RP Vignettes & Roadside Hooks**, and **Random/Scripted Encounter Interceptions** that pause the journey at the exact route coordinate to resolve in MUD or 2.5D Tactical Grid before clicking `[Resume Journey]`); and **(3) Seamless On-the-Fly Mode Switching** (switch between Point-to-Point road travel and off-road Hex-Crawl at any time).

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Enforced by phase DoD suites (`pytest -m zero_ai`, `tools/lint_agnosticism.py`, `tools/lint_modularity.py`, and `import-linter`) as implementation lands.
