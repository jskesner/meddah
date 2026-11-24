# 0043. Premade Map & Module Cartography Ingestion, Vision Transposition & World Splicing

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Architectural Decision #43 (`docs/design/system_design_specification.md`)

## Context & Problem Statement
Architectural design constraint and domain resolution for **Premade Map & Module Cartography Ingestion, Vision Transposition & World Splicing** in Meddah: The Universal Story Engine.

## Decision
**Multi-Format Map Ingestor, Dual MUD+VTT Transposition Studio & Multi-Floor Engine (`map_and_module_cartography_ingestor.py` & `multi_floor_dungeon_graph.py`)**: **(1) Multi-Format Map & Module Import** (extracts embedded maps + keyed room descriptions directly from **PDF Adventure Modules**, standalone **Image Maps [`PNG/WEBP/JPG/SVG`]**, and native **VTT Cartography Formats [`.dd2vtt / .uvtt`, Foundry Scene JSON, Watabou/Azgaar JSON, Tiled `.tmj`]** with pre-built walls/lights/doors); **(2) Dual MUD + 2.5D VTT Transposition** (auto-calibrates square/hex grids via FFT/3-point drag, traces 2.5D walls/doors/local elevation, runs OCR/VLM on numbered room keys [`1`, `2`, `14a`] to segment **VTT Room Bounding Polygons $\leftrightarrow$ Navigable MUD Room Nodes & Exits**, and binds module read-aloud text, traps, loot, and `.rpgrules` monsters); **(3) Player-Safe Map Scrubber** (auto-inpaints/masks GM-only `"S"` secret door markers, `"T"` trap icons, and room numbers on the Player Canvas while keeping them clickable on the GM Layer); **(4) Multi-Scale World Splicing** (drop an imported dungeon onto any Overworld Hex/City Block, replace a `Scale 3` town map, or stitch a `Scale 1/2` regional hex map onto a neighboring border with 1-click faction/lore adaptation); and **(5) Arbitrary-Depth Multi-Floor Traversal Without Changing `Z-Strata`** (decouples macro planetary `Z-Strata` [`Z-2..Z+2`] from local `Scale 4` **Dungeon/Tower Floor Graphs [`floor_index: 1..N / B1..BN`]**, supporting both **Same-Canvas Side-by-Side Multi-Floor Maps** and **Linked Multi-Floor Deck Stacks** with cross-floor stair/shaft Line-of-Sight and split-party floor tracking—all inside the same `Z-Stratum`).

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Enforced by phase DoD suites (`pytest -m zero_ai`, `tools/lint_agnosticism.py`, `tools/lint_modularity.py`, and `import-linter`) as implementation lands.
