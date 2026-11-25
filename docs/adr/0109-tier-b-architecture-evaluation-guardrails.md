# 0109. `Tier B` (7–14B Local LLM via Ollama, 8–16GB VRAM) Architecture & Evaluation Guardrails

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Design Resolution #59 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **`Tier B` (7–14B Local LLM via Ollama, 8–16GB VRAM) Architecture & Evaluation Guardrails**.

## Decision
- **Pinned Reference Model Family**: Pin a primary open-weights reference family (e.g., `Qwen 2.5 / Qwen 3 7B–14B` via Ollama) as the golden Phase 2 / Phase 4 benchmark, plus smoke-test 1 secondary family (`Llama 3.1 / 3.2 8B`) to prevent prompt overfitting, keeping the model tag configurable in `.env` / `pyproject.toml`.
   - **Pinned Reference Model Family**: Pin a primary open-weights reference family (e.g., `Qwen 2.5 / Qwen 3 7B–14B` via Ollama) as the golden Phase 2 / Phase 4 benchmark, plus smoke-test 1 secondary family (`Llama 3.1 / 3.2 8B`) to prevent prompt overfitting, keeping the model tag configurable in `.env` / `pyproject.toml`.
   - **Dual-Mode Grammar-Constrained JSON + Streaming Narrator Split**: Use Ollama's native grammar-constrained JSON Schema (`format: <json_schema>`) for mechanical tool proposals so syntax errors are impossible, paired with a lightweight streaming prose pass (or a `<narration> + <tool_calls_json>` envelope with a tolerant JSON repair parser for models without native grammar support).
   - **Hybrid Phase 6 Evaluation Scoring**: 100% deterministic checks for rules/mechanics fidelity (tool-call validity, state consistency, clue coverage, latency/token budget) + an independent secondary `Tier B` local judge model (with a strict 1–5 evidence rubric) for narrative coherence/tone + human playtest sign-off checklist.
   - **Zero-VRAM Default Retrieval in `Tier B`**: Default strictly to **SQLite FTS5 BM25 + entity/tag/rule-ID lookup** in both `Tier A` and `Tier B` (requiring `0` extra VRAM or embedding models), with local vector embeddings (`nomic-embed-text` / `ChromaDB`) as an optional opt-in enhancement.
   - **Deterministic-First Phase 2 Ingestion Pipeline**: Run the `Tier A` deterministic structural heading/table/stat-block parser FIRST to extract structured tables and isolate targeted 1k–2k token text chunks, then pass only those targeted chunks through Domain-Specific `Tier B` Micro-Probes using grammar-constrained JSON schemas with per-probe checkpointing.
   - **Zero-Bottleneck Companion Execution**: Active combat uses the `<1ms` Deterministic Tactical Utility Evaluator for all companion mechanical turns/rolls + disposition bark templates, invoking a single coalesced `Tier B` micro-prompt only on high-drama narrative beats or direct conversation.
   - **Zero-Stall Scene Memory & JIT World Expansion**: Scene transitions immediately commit a `<5ms` deterministic `DeedFact`/event digest and expand stub rooms deterministically via `procedural_jit_expander.py` (`<5ms`), running `Tier B` episodic summarization or prose polish asynchronously in the background when the GPU queue is idle; `Tier A -> Tier B` hot-swaps read directly from the `DeedFact` ledger.
   - **Single-GPU Resource Coordinator (`gpu_resource_coordinator.py`) & Priority Local LLM Queue (`local_llm_queue.py`)**: On 8–16GB GPUs, default images to Procedural SVGs and TTS to lightweight CPU/low-VRAM `Piper`/`Kokoro` (`~100–300MB`) so the 7–14B LLM stays hot in VRAM (sequencing optional ComfyUI in `"On-Demand Portrait / Map Only"` mode); coalesce near-simultaneous scene actions (`~150ms`) into one prompt and schedule split-party/background calls via a priority queue with a 1-click `[Resolve Deterministically Now]` bypass.
   - **Scoped Block-Slice Prompting in Ruleset Studio**: Send only the 3–8 referenced blocks + a ~500-token Ruleset Signature Header and require a grammar-constrained JSON Patch validated by the deterministic Schema Linter & Monte Carlo Simulator.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
