# 0125. Scoped Multi-Page SRD/Wiki URL Discovery & Polite Anti-DDoS Fetching (`backend/app/ingestion/url_ingestor.py` & `URLSubpageSelectorModal` — Phase 2 & Phase 6 [MVP], Volume 1 §1.2.1 & Development Workflow §8.3)

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Grill-Me Resolution #75 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Scoped Multi-Page SRD/Wiki URL Discovery & Polite Anti-DDoS Fetching (`backend/app/ingestion/url_ingestor.py` & `URLSubpageSelectorModal` — Phase 2 & Phase 6 [MVP], Volume 1 §1.2.1 & Development Workflow §8.3)**.

## Decision
- **Two-Phase Index Discovery & Interactive Sub-Page Checklist**: Entering an SRD or wiki index URL with `--discover-links` fetches only the index page first, extracts outbound links confined strictly to the **same origin and URL path prefix** (`max_depth: 1..2`), and presents an **Interactive Chapter/Sub-Page Checklist** (`max_pages_per_job`, default: `25`) so the user explicitly chooses which sub-pages to ingest (never running an uncontrolled crawler).
   - **Two-Phase Index Discovery & Interactive Sub-Page Checklist**: Entering an SRD or wiki index URL with `--discover-links` fetches only the index page first, extracts outbound links confined strictly to the **same origin and URL path prefix** (`max_depth: 1..2`), and presents an **Interactive Chapter/Sub-Page Checklist** (`max_pages_per_job`, default: `25`) so the user explicitly chooses which sub-pages to ingest (never running an uncontrolled crawler).
   - **Polite Anti-Spam / Anti-DDoS Fetch Policy (`PoliteFetchPolicy`) & Graceful Human-in-the-Loop Challenge Recovery**: Fetches selected sub-pages strictly one at a time (`max_concurrent_requests: 1`) with a `1.5s–3.0s` jittered inter-request delay, honors `robots.txt` (`Disallow` and `Crawl-delay`) and `<meta name="robots">`, uses content-addressed local snapshots with `ETag`/`Last-Modified` conditional requests for zero-bandwidth resume, and obeys HTTP `429`/`503` `Retry-After` backoff. If a remote host presents any CAPTCHA or anti-bot challenge, automated fetching **immediately pauses in place** (preserving all already-fetched pages and never attempting to solve or bypass programmatically) and offers **3 Graceful Human-in-the-Loop Recovery Paths**: (1) *Visible Human Verification Window* in the Desktop App so the human user can complete the challenge directly in a visible browser window and click `[Capture Loaded Page & Resume Queue]`, (2) *Inline Paste / Drag-and-Drop Sub-Page Replacement Slot* so the user can open the URL in their regular browser and paste/drop the text, HTML, or saved file directly into that paused sub-page row (retaining full URL/anchor citation metadata), or (3) *Skip / Defer Individual Sub-Page* to continue staging the rest of the job.
   - **Unified Multi-Page Normalization & Anchor Citations**: Normalizes all selected pages into a Table-of-Contents-ordered Structural Document AST for cross-page reference resolution while preserving each extracted block's exact sub-page URL and `#heading` anchor in `source_citation`.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
