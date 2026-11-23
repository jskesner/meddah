# 0101. Printable Character Sheets

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Grill-Me Resolution #51 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Printable Character Sheets**.

## Decision
Each ruleset's sheet layout schema also defines a print template, rendered to HTML and exported to PDF via Chromium print in Electron, via the built-in pure-Python HTML-to-PDF renderer (`WeasyPrint` / `ReportLab` / `fpdf2`) on a Headless Server / Docker container, or via client-side `@media print` in the Browser Light Client. Variants: Blank (for pen-and-paper), Filled (current state), Compact/Full. Print-friendly high-contrast, ink-saving styling; tagged PDF where feasible. Also exportable: character JSON templates and companion/retinue cards. Rulesets without a print template get an auto-generated generic layout.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
