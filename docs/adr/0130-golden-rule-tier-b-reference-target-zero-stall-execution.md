# 0130. Golden Rule #3: `Tier B` (7–14B Local LLM via Ollama, 8–16GB VRAM) Reference Target & Zero-Stall Execution

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Golden Rule #3 (`docs/design/system_design_specification.md`)

## Context & Problem Statement
Non-negotiable invariant defining **Golden Rule #3: `Tier B` (7–14B Local LLM via Ollama, 8–16GB VRAM) Reference Target & Zero-Stall Execution** across all engine layers and phases.

## Decision
When AI is enabled, **Meddah** is engineered specifically around a **`Tier B` (7–14B Local LLM via Ollama on an 8–16GB VRAM consumer GPU)** baseline—never requiring a `Tier C` Cloud / Frontier API:
* **4k–8k Token JIT Micro-Prompts & Grammar-Constrained Tool Calls**: All AI prompts are tightly bounded to 4k–8k tokens and use Ollama's native grammar-constrained JSON Schema (`format: <json_schema>`) for mechanical tool proposals paired with a streaming prose pass.
* **Zero-VRAM Default Retrieval (`SQLite FTS5 BM25`) & Single-GPU Resource Coordination (`gpu_resource_coordinator.py`)**: Compendium lookup defaults to `0`-VRAM SQLite FTS5 BM25 + entity/tag indexing across both `Tier A` and `Tier B`; on single-GPU systems, images default to instant Procedural SVGs and TTS to lightweight CPU/low-VRAM `Piper`/`Kokoro` (`~100–300MB`) so the 7–14B LLM stays hot in VRAM.
* **Deterministic-First, Zero-Stall Gameplay**: Companion combat turns (`<1ms` utility evaluator), unexpanded room/POI JIT stub entry (`<5ms` `procedural_jit_expander.py`), and scene-end memory digests (`<5ms` `DeedFact` ledger) always execute deterministically first so navigation and combat never stall waiting for local GPU inference—streaming `Tier B` prose embellishments, coalesced high-drama companion banter, and idle background memory consolidation asynchronously via `local_llm_queue.py`.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Enforced continuously in CI via `tools/lint_agnosticism.py`, `tools/lint_modularity.py`, `import-linter`, and `pytest -m zero_ai`.
