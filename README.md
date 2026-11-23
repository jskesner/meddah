# Meddah: The Universal Story Engine

> [!NOTE]
> **Pre-Code Design & Repository Scaffolding Phase**: Architecture, modular specifications (§1.0–§1.29), engineering standards, and the 14-phase roadmap are locked in [`docs/design/`](./docs/design/). Implementation begins in **Phase 1 [MVP]**.

**Meddah** (CLI binary: `meddah`) is a tabletop-agnostic engine blending a **rich hypertext MUD** and an interactive **2.5D Virtual Tabletop (VTT)**, driven by a deterministic **Universal Ruleset Virtual Machine** and optionally augmented by context-efficient local (`Tier B` 7–14B via Ollama) or cloud (`Tier C`) AI storytellers.

## Core Design Principles (The 4 Golden Rules)

1. **Zero-Assumption Agnosticism**: Engine core never hardcodes `"HP"`, `"AC"`, `"STR"`, `"d20"`, `"Levels"`, or `"Spell Slots"`. Every mechanic executes declaratively from schemas (`.rpgrules`), validated across 7 disparate tabletop paradigms (`d20`, `d100`, `2d6/clocks`, dice pools, step/symbol dice, resource-wager card draw, and zero-stat rules-light narrative).
2. **100% Deterministic & Zero-AI Usability (`Tier A`)**: Every subsystem—ingestion, GM adjudication (with Solo Oracle + topic-chip dialogue brokers), companion tactics, procedural room/world expansion, Studios, and media fallbacks—works end-to-end with **zero LLM calls** (`AI_PROVIDER=none`) and includes runtime circuit-breaker failover.
3. **`Tier B` Local LLM Reference Target & Zero-Stall Execution**: When AI is enabled, prompts stay within `4k–8k` tokens using SQLite FTS5 BM25 retrieval (`0` extra VRAM), grammar-constrained JSON Schema tool proposals, and asynchronous narrative streaming so deterministic actions never stall.
4. **Modular, Opt-In & Dormant-Unless-Specified (`§1.0`)**: Only the Ruleset VM, event-sourced persistence, deterministic MUD parser, and Module Registry are non-optional. Optional subsystems register via `MeddahModule` manifests, stay `dormant` unless the ruleset supplies required primitives, ship with RAW (*Rules as Written*) defaults, and preserve replay integrity across live toggles.

## Delivery Targets

- **Standalone Desktop Application (`desktop/`)**: Electron + React + TypeScript + PixiJS desktop workstation managing an embedded Python sidecar or connecting remotely as a Host/GM Studio.
- **Headless Server & Unified Browser Web Client (`backend/`)**: Pure-Python installable server daemon (`meddah serve` supporting both table hosting and multi-tenant `--mode guild-server` West Marches hubs) with CLI management and container deployment profiles (`docker/`).

## Documentation & Roadmap

- **[`ROADMAP.md`](./ROADMAP.md)** — Authoritative milestone tracker (`Phases 1–6 + 2.5 [MVP]` contiguous first, `Phases 7–14 [Post-MVP]` modular expansions; staying on `v0.x.0` until all 14 planned phases complete, then tagging `v1.0.0`).
- **[`docs/design/system_design_specification.md`](./docs/design/system_design_specification.md)** — Executive Summary, 4 Golden Rules, and all 50 Locked Architectural Decisions.
- **[`docs/design/technical_specification_and_plan.md`](./docs/design/technical_specification_and_plan.md)** — Master Technical Index, §1.0 Module Registry, 14-Phase Implementation Plan, and 77 Grill-Me Resolutions.
- **[`docs/design/development_workflow_and_repository_standards.md`](./docs/design/development_workflow_and_repository_standards.md)** — Monorepo layout, layer boundaries (`import-linter`), CI gates, agnosticism/modularity linters, and ADR governance.
- **[`docs/CONTRIBUTING.md`](./docs/CONTRIBUTING.md)** — Contributor workflow, commit format, and testing requirements.

## Licensing & User-Content Boundary

Meddah engine source code is licensed under the **GNU Affero General Public License v3.0 ([`LICENSE`](./LICENSE))** (`AGPL-3.0-only`).

User-authored or third-party data packages—including **`.rpgrules`**, **`.rpgworld`**, **`.rpgcampaign`**, **`.rpgcharacter`**, **`.rpgtileset`**, **`.rpgtheme`**, **`.rpgprofile`**, and **`.rpgcompetition`** archives loaded into or exported by Meddah—are treated strictly as **user content / data**, remain **100% owned and licensed under whatever terms their respective creators choose**, and are not bound by the engine's AGPL-3.0 license.
