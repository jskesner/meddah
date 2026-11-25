# 0074. Hardware Capability Tiers (Unified 3-Tier Model)

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Design Resolution #24 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Hardware Capability Tiers (Unified 3-Tier Model)**.

## Decision
Detected at first run and re-checkable in Settings.
   - **`Tier A` (Zero-AI / 100% Deterministic)**: No LLM (`AI_PROVIDER=none`); complete deterministic play via `deterministic_gm_director.py`, `deterministic_dialogue_broker.py`, `improvised_stunt_resolver.py`, `canonical_deed_ledger.py`, and the Solo RPG Oracle.
   - **`Tier B` (Local LLM Reference Baseline — 7–14B via Ollama, ~8–16GB VRAM)**: **Our primary design target** for the full MVP AI experience, all 4k–8k token JIT Micro-Prompts, and the **Phase 2 & Phase 4 LLM evaluation gates**. Includes an automatic **`Tier B-Lite` (3–8B or CPU-only)** sub-profile that restricts AI to structured tasks with a 2–4k token budget and routes multi-NPC impulses and heavy ingestion to deterministic fallbacks.
   - **`Tier C` (Cloud / Frontier API or Large 30B–70B+ Local Models)**: Optional upgrade tier with expanded context and multi-agent polish; never required for any feature or phase gate.
   - The UI shows the active tier and per-feature availability instead of failing silently, and supports **bidirectional mid-campaign hot-swapping (`Tier A <-> Tier B <-> Tier C`)** without losing narrative continuity.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
