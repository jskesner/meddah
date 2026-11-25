# 0127. Themeable & `.rpgworld`-Configurable Diegetic Timepiece Widget & Time-of-Day Color-Shifting (`TimepieceWidget.tsx` & `TimeOfDayColorLUT` — Phase 6 [MVP], [Vol 3, §1.5 item 6A](./tech_spec_03_world_cosmology_and_society.md) & [Vol 4, §1.8 item 2](./tech_spec_04_multiplayer_ui_and_vtt.md))

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Design Resolution #77 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Themeable & `.rpgworld`-Configurable Diegetic Timepiece Widget & Time-of-Day Color-Shifting (`TimepieceWidget.tsx` & `TimeOfDayColorLUT` — Phase 6 [MVP], [Vol 3, §1.5 item 6A](./tech_spec_03_world_cosmology_and_society.md) & [Vol 4, §1.8 item 2](./tech_spec_04_multiplayer_ui_and_vtt.md))**.

## Decision
- **Diegetic Timepiece Widget**: Animated in-game time-telling instrument (sundial, celestial orrery, pocket watch/moon-dial, digital/Nixie chronometer, phosphor ASCII clock, or hourglass) reflecting exact world time across arbitrary custom day lengths. Visual style defaults to the active `.rpgtheme`'s `timepiece_skin`, can be overridden per `.rpgworld` (`timepiece_style`), and automatically hides/masks when characters lack chronometry underground or in timeless planes.
    - **Diegetic Timepiece Widget**: Animated in-game time-telling instrument (sundial, celestial orrery, pocket watch/moon-dial, digital/Nixie chronometer, phosphor ASCII clock, or hourglass) reflecting exact world time across arbitrary custom day lengths. Visual style defaults to the active `.rpgtheme`'s `timepiece_skin`, can be overridden per `.rpgworld` (`timepiece_style`), and automatically hides/masks when characters lack chronometry underground or in timeless planes.
    - **Time-of-Day Ambient Color-Shifting (`TimeOfDayColorLUT`)**: Smoothly interpolates Dawn $\rightarrow$ Midday $\rightarrow$ Dusk $\rightarrow$ Night (plus multi-sun/moon/eclipse hues) across 2.5D VTT tiles and backdrops, configurable per `.rpgworld` and `.rpgtheme`, strictly respecting room `exposure_type` (`deep_indoor` stays insulated) and automatically clamping/disabling under WCAG 2.2 AA High-Contrast accessibility presets.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
