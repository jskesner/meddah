# 0073. Accessibility Verification

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Grill-Me Resolution #23 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Accessibility Verification**.

## Decision
Automated + manual. CI runs axe-core and Playwright checks on key screens (contrast tokens, focus order, ARIA landmarks, reduced-motion); every theme preset must pass a contrast-ratio unit test; a manual checklist covers VTT grid readout and live-region narration with Orca (Linux) and NVDA/VoiceOver as platforms are added. Accessibility is a release gate. The claim is "WCAG 2.2 AA verified, AAA where feasible"; earlier unqualified "WCAG AAA" wording has been updated to this claim (the High-Contrast theme's >7:1 contrast target remains AAA-level).

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
