# 0124. Host-Created Custom MUD Commands, Declarative `ECA` Action Chains, Custom 3-Perspective Social Emotes & Player Shorthand Aliases (`backend/app/mud_parser/custom_commands.py` & `CustomCommandAndEmoteStudio.tsx` — Phase 1 & Phase 6 [MVP], Volume 4 §1.7.4.G & Decision #3)

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Grill-Me Resolution #74 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Host-Created Custom MUD Commands, Declarative `ECA` Action Chains, Custom 3-Perspective Social Emotes & Player Shorthand Aliases (`backend/app/mud_parser/custom_commands.py` & `CustomCommandAndEmoteStudio.tsx` — Phase 1 & Phase 6 [MVP], Volume 4 §1.7.4.G & Decision #3)**.

## Decision
- **Live Host-Created Parameterized Social Emotes (`CustomEmoteBlock`)**: Hosts and Host-authorized GMs can create custom 3-perspective social emotes (*To Actor*, *To Target*, *To Room*) across untargeted and `@target` invocations with `{actor}`, `{target}`, `{adverb}`, and `"{speech}"` interpolation, optional **Semantic Valence Tags** (driving deterministic `Tier A` and `Tier B/C` NPC/Companion reactions), optional AST prerequisite gates, and optional `audio_clip_ref` SFX or VTT particle cues.
   - **Live Host-Created Parameterized Social Emotes (`CustomEmoteBlock`)**: Hosts and Host-authorized GMs can create custom 3-perspective social emotes (*To Actor*, *To Target*, *To Room*) across untargeted and `@target` invocations with `{actor}`, `{target}`, `{adverb}`, and `"{speech}"` interpolation, optional **Semantic Valence Tags** (driving deterministic `Tier A` and `Tier B/C` NPC/Companion reactions), optional AST prerequisite gates, and optional `audio_clip_ref` SFX or VTT particle cues.
   - **Host-Created Custom MUD Commands & 4-Step Declarative `ECA` Pipelines (`CustomMudCommandBlock` & `CommandActionPipeline`)**: Never executes arbitrary Python/JS code; instead chains up to 4 sandboxed, replay-safe Ruleset VM `ECA` steps: (1) *AST Precondition & Cost Gate* (`requires` & `costs` with custom failure notice), (2) *Optional Skill Check, Target Confirmation Prompt, or Table Roll* (`on_success` / `on_partial` / `on_failure`), (3) *Ordered Deterministic Payloads* (3-perspective MUD text/SFX/VFX, condition/pool/inventory mutations, room contraption/clock/portal triggers, or Handout/UI drawer popups), and (4) *Optional Interruptible Channeling Condition* (`channel_duration`).
   - **RBAC Governance, Scope & Player Shorthand Aliases**: Controlled by the Host and Host-authorized GMs (`can_manage_custom_commands`), scoped to room/POI, region/hub, campaign overlay, guild server, or `.rpgrules`/`.rpgworld` packages with instant live sync to connected players' `/` autocomplete palette; individual players can also define client-side `> alias` shorthand macros that expand into server-validated MUD commands.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
