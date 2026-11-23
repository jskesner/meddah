# 0099. End-of-Session Pipeline & Reports

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Grill-Me Resolution #49 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **End-of-Session Pipeline & Reports**.

## Decision
Triggered by the transition to `Ended`; ordered, idempotent steps with a visible progress panel: (1) final checkpoint and backup; (2) deterministic mechanical summary from events (XP, loot, quest changes, deaths, rolls, time passed) with no LLM; (3) episodic/hierarchical memory consolidation; (4) optional AI narrative recap and "Previously On..." text (skipped in Tier A); (5) per-player and GM reports; (6) export to a `reports/` folder in the campaign. Reports: Session Summary in Markdown, HTML, and PDF (rendered via Chromium print in the Electron app, or via the built-in lightweight pure-Python PDF renderer `WeasyPrint` / `ReportLab` / `fpdf2` in Headless Server / Docker mode so zero headless-browser bloat is required), with a player-safe version (no GM-only secrets) and a GM version. Steps can fail or be skipped independently, and reports can be regenerated later from the event log.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
