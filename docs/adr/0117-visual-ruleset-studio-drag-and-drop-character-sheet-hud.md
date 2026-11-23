# 0117. Visual Ruleset Studio — Drag-and-Drop Character Sheet/HUD Layout Designer & Safe In-Campaign Hot-Reloading (`SheetLayoutDesigner.tsx` & `ruleset_hot_reload.py` — Phase 6 [MVP], Volume 1 §1.2.5)

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Grill-Me Resolution #67 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Visual Ruleset Studio — Drag-and-Drop Character Sheet/HUD Layout Designer & Safe In-Campaign Hot-Reloading (`SheetLayoutDesigner.tsx` & `ruleset_hot_reload.py` — Phase 6 [MVP], Volume 1 §1.2.5)**.

## Decision
- **Integrated Drag-and-Drop Sheet & HUD Layout Tab**: Alongside mechanical building blocks, the Visual Ruleset Studio includes a visual **Sheet & HUD Layout Designer** tab where designers drag properties, derived stats, resource bars/clocks, paper-doll/hit-location silhouettes, layered equipment slots, and capability tabs onto a responsive grid canvas (with an automatic category-based layout fallback if a ruleset author skips custom layout design).
   - **Integrated Drag-and-Drop Sheet & HUD Layout Tab**: Alongside mechanical building blocks, the Visual Ruleset Studio includes a visual **Sheet & HUD Layout Designer** tab where designers drag properties, derived stats, resource bars/clocks, paper-doll/hit-location silhouettes, layered equipment slots, and capability tabs onto a responsive grid canvas (with an automatic category-based layout fallback if a ruleset author skips custom layout design).
   - **Safe In-Campaign Hot-Reloading with Auto-Checkpoint**: When a Host/GM or Solo Player edits a ruleset or adds a homebrew block in the Studio while a campaign is in progress, clicking **`[Hot-Reload / Apply to Active Campaign]`** automatically creates a pre-migration event-store checkpoint, validates state compatibility (prompting for default values on newly added properties), commits a versioned `RULESET_MIGRATED` event, and hot-reloads the active sheet/VM without requiring a new campaign.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
