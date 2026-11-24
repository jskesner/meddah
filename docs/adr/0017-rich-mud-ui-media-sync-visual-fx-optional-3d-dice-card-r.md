# 0017. Rich MUD UI, Media Sync, Visual FX & Optional 3D Dice / Card Randomizers

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Architectural Decision #17 (`docs/design/system_design_specification.md`)

## Context & Problem Statement
Architectural design constraint and domain resolution for **Rich MUD UI, Media Sync, Visual FX & Optional 3D Dice / Card Randomizers** in Meddah: The Universal Story Engine.

## Decision
**Hypertext MUD Log + Progressive Media + Event-Sourced Branching + Post-MVP Kinetic VFX & Randomizers (`visual_fx/` & `dice_tray/`)**: Clickable entity/item/exit links and expandable roll cards in the MUD log; non-blocking progressive TTS/Image streaming; event-sourced checkpoints allowing turn rewind and "What-If" campaign timeline branching; bundled with **3 Showcase Sample Rulesets** (`d20`, `d100`, `2d6/Clock`). **Post-MVP Visual Polish (Phase 13)** adds: **(1) Multi-State Character Portraits & Universal Modular Condition Shaders (`ConditionVisualSpec`)** (`Tier A` Layered Paper-Doll SVG Composer, custom multi-expression packs, optional AI variants, Vitality state swaps [`Healthy -> Bloodied -> Critical -> Dead`], and a **Universal Composable Condition Shader Schema** built from 7 primitives—*Color Grade, Procedural Border, UV Distortion, Particle Emitter, Stack-Scaling Texture Mask, Transform Motion, and Custom GLSL/SVG*—that **priority cross-fades** cohesive condition shaders without slot-mixing when multiple conditions are active while displaying all active mini-icon badges); **(2) 3 Tactical VTT Token Styles Linked by Default to Portrait States/Shaders** (with optional custom sprite override); **(3) 100% Optional Authoritative 3D Physics Dice (`Three.js` + `Rapier3D`) & Multi-Scope Card-Deck / Hand Visualizer (`CardDeckVisualizer.tsx`)** (shared multiplayer sync for public rolls + private/blind roll masking, supporting `table_shared`, `per_entity`, and `encounter_local` decks with shrinking Draw Stacks, Discard Piles, and dynamic Fan-Layout Player Hands); and **(4) Dual-Tier VFX Toggles (`CampaignVisualPolicyBlock` + `ClientVisualPreferences`)**.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Enforced by phase DoD suites (`pytest -m zero_ai`, `tools/lint_agnosticism.py`, `tools/lint_modularity.py`, and `import-linter`) as implementation lands.
