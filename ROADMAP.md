---
project: meddah
version_policy: pre-1.0-until-all-14-phases-complete
phases:
  - id: P1
    name: Core Agnostic Ruleset VM, Module Registry, Layered Inventory, Creation/Advancement & MUD Parser
    mvp: true
    status: Done
    target_release: v0.1.0
    spec: ./docs/design/tech_spec_01_core_vm_and_ingestion.md
  - id: P2
    name: Ruleset Ingestion Pipeline, 14-Domain Semantic Probes, AI Co-Designer & Diff Workbench Backend
    mvp: true
    status: Planned
    target_release: v0.2.0
    spec: ./docs/design/tech_spec_01_core_vm_and_ingestion.md
  - id: P2.5
    name: Early Thin Playable Slice (Terminal CLI MUD & Headless Server Daemon)
    mvp: true
    status: Planned
    target_release: v0.2.5
    spec: ./docs/design/technical_specification_and_plan.md
  - id: P3
    name: Event-Sourced Persistence, Multi-Scale Cosmology, Multi-Floor Dungeons & Living World Chronology
    mvp: true
    status: Planned
    target_release: v0.3.0
    spec: ./docs/design/tech_spec_03_world_cosmology_and_society.md
  - id: P4
    name: Context-Efficient AI GM, Deterministic Solo/GM Director, RAW-Default Mercy & Quest Storyboard
    mvp: true
    status: Planned
    target_release: v0.4.0
    spec: ./docs/design/tech_spec_02_agents_companions_and_quests.md
  - id: P5
    name: Host-Authoritative Multiplayer, Split-Party Engine, Content Safety & Multimodal Media Pipeline
    mvp: true
    status: Planned
    target_release: v0.5.0
    spec: ./docs/design/tech_spec_04_multiplayer_ui_and_vtt.md
  - id: P6
    name: Desktop Shell, Unified Web Client, Hypertext MUD, 2.5D VTT, Timepiece/LUT & Visual Studios
    mvp: true
    status: Planned
    target_release: v0.6.0
    spec: ./docs/design/tech_spec_04_multiplayer_ui_and_vtt.md
  - id: P7
    name: Autonomous AI Companions, Morale/Confrontations & 5-Category Permanent Retinue
    mvp: false
    status: Planned
    target_release: v0.7.0
    spec: ./docs/design/tech_spec_02_agents_companions_and_quests.md
  - id: P8
    name: Overworld Travel, Megacities, Geopolitics, Law/Capture & Random Encounters
    mvp: false
    status: Planned
    target_release: v0.8.0
    spec: ./docs/design/tech_spec_03_world_cosmology_and_society.md
  - id: P9
    name: Rest/Downtime, Crafting/Survival, Loot/Commerce/Trade, Contraptions & Piety/Patrons
    mvp: false
    status: Planned
    target_release: v0.9.0
    spec: ./docs/design/tech_spec_05_gameplay_systems_and_anatomy.md
  - id: P10
    name: Player Holdings/Strongholds, Pilotable Vehicles & Granular Hit Location/Surgery Engine
    mvp: false
    status: Planned
    target_release: v0.10.0
    spec: ./docs/design/tech_spec_05_gameplay_systems_and_anatomy.md
  - id: P11
    name: Premade Map/Module Cartography Ingestion, Custom Tilesets, Mass Warfare & Curveballs
    mvp: false
    status: Planned
    target_release: v0.11.0
    spec: ./docs/design/tech_spec_04_multiplayer_ui_and_vtt.md
  - id: P12
    name: Universal Chase, Pursuit, Race, Moving-Battle & Competition/Festival Circuit Engines
    mvp: false
    status: Planned
    target_release: v0.12.0
    spec: ./docs/design/tech_spec_05_gameplay_systems_and_anatomy.md
  - id: P13
    name: Map/Tileset Studios, Live GM Dock, 4-Bus Spatial Audio & 3D Dice/Card Visual FX
    mvp: false
    status: Planned
    target_release: v0.13.0
    spec: ./docs/design/tech_spec_04_multiplayer_ui_and_vtt.md
  - id: P14
    name: Universal West Marches Campaign Engine (All Play Modes) & Persistent Guild Server Daemon
    mvp: false
    status: Planned
    target_release: v0.14.0
    spec: ./docs/design/tech_spec_04_multiplayer_ui_and_vtt.md
---

# Meddah Implementation Roadmap

> Authoritative single source of truth for phased delivery. Full technical specifications live in [`docs/design/technical_specification_and_plan.md`](./docs/design/technical_specification_and_plan.md).
> **Versioning Policy**: Minor tags advance `v0.1.0` through `v0.14.0` per phase milestone, remaining on `0.x.0` until all 14 planned phases are complete (`v1.0.0`).

---

## Track A — Contiguous MVP Phases (`P1`–`P6` + `P2.5`)

### [P1] Phase 1: Core Agnostic Ruleset VM, Module Registry, Layered Inventory, Creation/Advancement & MUD Parser
- **Status**: `Done` | **MVP**: `Yes` | **Target Tag**: `v0.1.0`
- [x] `backend/app/ruleset_vm/`: Safe AST evaluator (`0` eval/exec), named seeded RNG streams, flow controller (`freeform` / `round_initiative` / `popcorn_spotlight`), reaction & contested windows, universal `inventory_graph.py` (`abstract_slots` & `anatomical_layered`), `advancement.py` (5 creation + 5 progression paradigms), `forms.py` (`FormBlock` alternate forms & transformations), and audited property/pool/condition/tag `SHEET_OVERRIDE` (`vm.py`).
- [x] `backend/app/ruleset_vm/module_registry.py` & `tools/lint_modularity.py` + `tools/lint_agnosticism.py`.
- [x] `backend/app/mud_parser/`: `<5ms` deterministic lexer, `social_dsl.py`, 60+ 3-perspective social emotes, `custom_commands.py` (host custom commands/emotes & 4-step declarative `ECA` pipelines), `diegetic_comms.py`.
- [x] 7 Conformance Ruleset fixtures (`3 Showcase + 4 Conformance`) & `pytest -m zero_ai` suite passing.

### [P2] Phase 2: Ruleset Ingestion Pipeline, 14-Domain Semantic Probes, AI Co-Designer & Diff Workbench Backend
- **Status**: `Planned` | **MVP**: `Yes` | **Target Tag**: `v0.2.0`
- [ ] `backend/app/ingestion/`: Sandboxed PDF/Markdown/JSON/YAML/CSV extractors, SQLite FTS5 BM25 indexer, JIT block compiler.
- [ ] `url_ingestor.py`: SSRF-protected single-URL & scoped multi-page discovery (`max_depth: 1..2`), interactive sub-page checklist, sequential `PoliteFetchPolicy`, and 3 graceful human-in-the-loop CAPTCHA recovery paths.
- [ ] `lifecycle_probes.py` (14 probes with explicit `Null/Absent` guarantee + alternate-form/`FormBlock` extraction), `ai_architect.py`, `balance_simulator.py`, and Staging Diff Workbench API.
- [ ] Dual-track ingestion evaluation gates (`Tier A` deterministic + `Tier B` Ollama).

### [P2.5] Phase 2.5: Early Thin Playable Slice (Terminal CLI MUD & Headless Server Daemon)
- **Status**: `Planned` | **MVP**: `Yes` | **Target Tag**: `v0.2.5`
- [ ] `backend/app/cli/`: Interactive terminal client (`meddah attach` — including manual-roll mode toggle, direct `SHEET_OVERRIDE` edits, and `form shift` / `form revert` commands) & server management CLI (`meddah serve`, `campaign`, `session`, `seat`, `backup`, `ruleset`, `gpu-check`).
- [ ] `docker/Dockerfile.server` & `docker/docker-compose.server.yml` (NVIDIA/AMD ROCm/Vulkan/CPU profiles).
- [ ] 30-minute interactive Zero-AI acceptance test across the 3 showcase rulesets.

### [P3] Phase 3: Event-Sourced Persistence, Multi-Scale Cosmology, Multi-Floor Dungeons & Living World Chronology
- **Status**: `Planned` | **MVP**: `Yes` | **Target Tag**: `v0.3.0`
- [ ] `backend/app/storage/`: WAL SQLite event store, snapshots/checkpoints, undo/rewind/timeline branching, `package_manager.py` (`.rpgrules`/`.rpgworld`/`.rpgcampaign`/`.rpgcharacter` + offline sheet export), `handout_store.py` (cipher/image/audio handouts, 3-tier journals, Fog-of-War Lore Codex), `chronicle_exporter.py`.
- [ ] `backend/app/world_gen/`: CoW overlays, Scales 0–4, `world_z_stratum`, `multi_floor_dungeon_graph.py`, `<5ms` `procedural_jit_expander.py`, `chronology.py`, `ambient_ticker.py`, faction clocks.

### [P4] Phase 4: Context-Efficient AI GM, Deterministic Solo/GM Director, RAW-Default Mercy & Quest Storyboard
- **Status**: `Planned` | **MVP**: `Yes` | **Target Tag**: `v0.4.0`
- [ ] `deterministic_gm_director.py`, `deterministic_dialogue_broker.py`, `improvised_stunt_resolver.py`, Solo Oracle tables, `canonical_deed_ledger.py`.
- [ ] `llm_router.py`, `local_llm_queue.py`, `ai_fallback_router.py` (`Tier A <-> Tier B` runtime circuit breaker), `context_budget.py`, `gm_difficulty_and_mercy_director.py` (strictly RAW default), `quest_director.py` & 3-Clue Matrix.

### [P5] Phase 5: Host-Authoritative Multiplayer, Split-Party Engine, Content Safety & Multimodal Media Pipeline
- **Status**: `Planned` | **MVP**: `Yes` | **Target Tag**: `v0.5.0`
- [ ] `backend/app/multiplayer/`: WebSocket JSON-RPC gateway, orthogonal `is_server_admin` + seat RBAC (including `can_direct_edit_sheet` and campaign-level `disable_player_facing_rolls`), FoW filtering, Waiting Room, 1-click Tunnel, Split-Party concurrent room queues.
- [ ] `backend/app/safety/` (Content Rating, Lines & Veils, X-Card) & `backend/app/media/` + `gpu_resource_coordinator.py` (Procedural SVG/paper-doll default, Piper/Kokoro TTS/blip synth).

### [P6] Phase 6: Desktop Shell, Unified Web Client, Hypertext MUD, 2.5D VTT, Timepiece/LUT & Visual Studios
- **Status**: `Planned` | **MVP**: `Yes` | **Target Tag**: `v0.6.0`
- [ ] `desktop/` Electron + React + TypeScript + PixiJS shell & Unified Browser Web Client (`meddah serve --serve-web-client`), 6 Themes (with `timepiece_skin` & `time_of_day_lut`), WCAG 2.2 AA (`axe-core` gate).
- [ ] Hypertext MUD terminal (Comms Pill Bar, channel tabs + FTS5 search, bookmarks, Chronicle Export, Pinned Hotbar, Remappable Keybindings, Workspace Presets, **`TimepieceWidget`**, Handouts/Journals/Codex Drawer, 5-step First-Run Onboarding Wizard).
- [ ] Core Multi-Scale & 2.5D Tactical VTT (`TimeOfDayColorLUT`, live Scale Pill/Caliper, LoS, 3-state FoW, AoE stencils, Map Pings/GM Camera Pull, Annotations & Sticky Pins, Turn/Initiative Tracker Strip).
- [ ] Dynamic Character Sheet (with inline direct-sheet `SHEET_OVERRIDE` edit mode, table roll-bypass toggle, and Form Switcher Pill + portrait/token auto-swap), Layered Inventory/Apparel UI, 3-Mode Builder, Advancement Drawer, 4-Tab Capabilities Deck, **Visual Ruleset Studio GUI + Compendium & Custom Command Studios**, and **Unified World/Dungeon/NPC/Dialogue/Oracle/Linter Studio**.

---

## Track B — Post-MVP Modular Expansion Phases (`P7`–`P14`)

- **P7** (`v0.7.0`, `Planned`): Autonomous AI Companions (`ai_npc.py`), Tactical Obedience, Confrontations/Mutiny, Revival/Succession & 5-Category Permanent Retinue (`retinue_engine.py`).
- **P8** (`v0.8.0`, `Planned`): Dual-Mode Overworld Travel, Megacities/Citadels, Geopolitics/Rebellions, Law/Witnesses/Capture & Context-Aware Random Encounters.
- **P9** (`v0.9.0`, `Planned`): Rest/Camping & Downtime, Crafting & Optional Survival Mode (with Default-On Ruleset Hostile Environments), 5-Source Loot & `EntityLootConfigBlock`, **In-Game Commerce, Haggling & Atomic Player-to-Player Trading (`commerce_and_trade.py`)**, Modular Puzzles/Traps/Wavefronts, and Piety/Patrons/Dreams.
- **P10** (`v0.10.0`, `Planned`): Unified Player Holdings/Strongholds & Pilotable Vessels, and 3-Topology Granular Hit Location, Medical Surgery & Prosthetic Engine (`hit_location_engine.py`, including `FormBlock` `anatomy_topology_override` swaps).
- **P11** (`v0.11.0`, `Planned`): Premade Map/Module Cartography Ingestor, Custom `.rpgtileset` Wang Auto-Tiler, Mass Warfare/Sieges & 5 Tactical Curveball Stress Fixtures.
- **P12** (`v0.12.0`, `Planned`): Universal Chase, Pursuit, Race & Moving-Battle Engine, plus Universal Competition, Minigame & Festival Circuit Engine.
- **P13** (`v0.13.0`, `Planned`): Map/Tileset Cartography Studios, Live GM World/Timeline Dock, 4-Bus Spatial Audio Director & Player Clip Broadcaster, Condition Shaders & Authoritative 3D Dice/Card Visual FX.
- **P14** (`v0.14.0`, `Planned`): Universal West Marches Campaign Engine (All Play Modes) & Headless Persistent Guild Server Daemon (`meddah serve --mode guild-server`).

---

## Deferred / Ideas

- Additional community `.rpgrules` showcase templates and localization packs (post-`v1.0.0`).
