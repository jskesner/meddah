# 0064. Package File Format (`.rpgrules` / `.rpgworld`)

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Grill-Me Resolution #14 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Package File Format (`.rpgrules` / `.rpgworld`)**.

## Decision
Zip container with `manifest.json` at the root (`type`, `schema_version`, `engine_min_version`, content hash, dependency list with version hashes, license/attribution, and `redaction` flags). Hand-editable content is one YAML (default) or JSON file per building block under `blocks/`; large catalogs use JSONL; assets are content-addressed under `assets/<sha256>`. The compendium FTS/vector index is NOT shipped and is rebuilt on import. Validation uses published JSON Schemas generated from the Pydantic models so external tools and VCS diffs work.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
