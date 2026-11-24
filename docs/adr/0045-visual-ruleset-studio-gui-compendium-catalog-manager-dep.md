# 0045. Visual Ruleset Studio GUI, Compendium Catalog Manager, Dependency Explorer, Inline Documentation Hub, Balance Simulator & Optional AI Ruleset Architect

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Architectural Decision #45 (`docs/design/system_design_specification.md`)

## Context & Problem Statement
Architectural design constraint and domain resolution for **Visual Ruleset Studio GUI, Compendium Catalog Manager, Dependency Explorer, Inline Documentation Hub, Balance Simulator & Optional AI Ruleset Architect** in Meddah: The Universal Story Engine.

## Decision
**100% Zero-AI Visual Ruleset IDE (`desktop/src/features/ruleset_studio/` — [MVP Phase 6]) + Opt-In AI Ruleset Co-Designer (`ruleset_ai_architect.py` & `RulesetCoDesignerDrawer`)**: **(1) Visual Drag-and-Drop Primitive Palette & Sheet Layout Designer** (searchable 7-category palette of all universal building blocks and 1-click subsystem pattern macros wired onto a `React Flow` node canvas with a no-code Visual Formula & Condition Clause Builder, synchronized YAML/JSON split view, integrated Drag-and-Drop Character Sheet/HUD Layout Designer tab, and safe in-campaign ruleset hot-reloading with auto-checkpoint); **(2) Visual Compendium, Item/Apparel, Capability & Bestiary Catalog Manager (`CompendiumCatalogStudio.tsx`)** (dual guided-card inspector and high-speed spreadsheet data-grid with CSV/Markdown-table copy-paste for bulk-authoring items, layered clothing/cosmetics/armor [`WearableLayerSpec`], spells/maneuvers/feats/stances/reactions [`CapabilityBlock`], conditions [`ConditionVisualSpec`], rollable loot/encounter tables, and Bestiary monsters with a 1-click `"Clone & Variant"` builder and per-creature loot/vitality topology overrides); **(3) Interactive Dependency Graph Explorer & Live §1.0 Module-Readiness Inspector** (highlights upstream/downstream references, propagates property renames safely across all formulas, flags broken/circular links, and displays a live checklist of which `MeddahModule` subsystems transition from `dormant` $\rightarrow$ `available`); **(4) Contextual Inline Documentation Hub & 7-Paradigm Showcase Example Cloner** (auto-generated field-by-field guides paired with a *"How Other Rulesets Do This"* side-by-side comparison tab across the 7 conformance rulesets and a 1-click `[Insert Example as Template]` button); **(5) Interactive Single-Block Test Scratchpad & Monte Carlo Balance Simulator** (mock `@self`/`@target` sliders, deterministic `explain_ast_deterministically()` plain-English walkthrough, live dice probability curve plotter, and `<500ms` 1,000-round headless combat/TTK simulations); and **(6) Strictly Optional, Diff-Gated AI Ruleset Co-Designer** (can be turned completely off for `0`-LLM visual authoring, or used for conversational system drafting, homebrew injection, and plain-English $\leftrightarrow$ AST formula translation staged through the Diff Review Workbench).

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Enforced by phase DoD suites (`pytest -m zero_ai`, `tools/lint_agnosticism.py`, `tools/lint_modularity.py`, and `import-linter`) as implementation lands.
