# 0044. Custom Map Tilesets, Smart Auto-Tiling & Semantic Prop Packs

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Architectural Decision #44 (`docs/design/system_design_specification.md`)

## Context & Problem Statement
Architectural design constraint and domain resolution for **Custom Map Tilesets, Smart Auto-Tiling & Semantic Prop Packs** in Meddah: The Universal Story Engine.

## Decision
**Universal `.rpgtileset` Studio, Auto-Tiler & Procedural Palette Engine (`tileset_and_autotile_engine.py` & `tileset_studio/`)**: **(1) Multi-Format Tileset Import & Slicer** (supports portable `.rpgtileset` bundles, `PNG/WEBP/SVG` sprite sheets with an interactive cell/padding slicer, **Flat/Pointy Hex Tilesets** with 2.5D overhang toppers, **Top-Down / 2.5D Oblique / Isometric** tiles, and direct import of **Tiled `.tsx/.tsj`**, **LDtk**, and **Wang / Blob-47 / 16-Tile** auto-tile sets); **(2) Smart Bitmask Auto-Tiling, Variants & Animated/State-Reactive Tiles** (automatic wall/corner/shoreline blending, weighted Perlin variants to prevent checkerboard repetition, animated water/lava/torches, and state-mutating tiles [`intact <-> destroyed`, `closed <-> open`]); **(3) "Smart Tile" Dual VTT+MUD Metadata** (each tile/prop pre-binds 2.5D Line-of-Sight occlusion, cover grade, movement cost, point lighting, and `TacticalHazardBlock` triggers **plus** MUD sensory tags and `Interactable/ContainerNode` templates); and **(4) Procedural/JIT Generation Binding & 1-Click Biome Palette Swapping** (cascading `World -> Region -> Settlement/Dungeon` tileset assignment so procedural/JIT rooms build with your custom tilesets and can re-skin palettes in one click).

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Enforced by phase DoD suites (`pytest -m zero_ai`, `tools/lint_agnosticism.py`, `tools/lint_modularity.py`, and `import-linter`) as implementation lands.
