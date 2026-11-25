# Changelog

All notable changes to **Meddah: The Universal Story Engine** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) (`0.x.0` per phase milestone until all 14 planned phases complete for `v1.0.0`).

## [Unreleased]

### Added
- **Universal Character Transformations & Alternate Forms (`backend/app/ruleset_vm/forms.py`, [ADR-0133](./docs/adr/0133-universal-character-transformations-and-alternate-forms.md))**: Added `FormBlock` and `FormPoolSpec` schemas (`schemas/form.schema.json`), runtime `ActiveFormState` (including `involuntary` and `source_entity_id` tracking) and `FORM_CHANGED` replay transitions (`shift_into_form`, `revert_form`, `tick_active_form`), declarative `shift_form`/`revert_form` `EffectSpec` actions and forced-transformation bypass/locks, bounded public `trigger_event_hooks` dispatching (`on_form_entered`, `on_form_reverted`, `on_condition_changed`), 3 property transformation modes (`replace_all`, `replace_subset`, `delta_overlay`), per-pool spillover/auto-revert policies, and gear/aura suppression controls.
- **Condition & Tag Overrides in `SHEET_OVERRIDE`**: Extended `apply_sheet_override()` with audited `add_conditions`, `remove_conditions`, `add_tags`, and `remove_tags` support plus explicit CLI/Multiplayer/GUI roadmap tracking across `P2.5`, `P5`, and `P6`.

### Changed
- Standardized "Design Resolutions" terminology across design specifications, `README.md`, and ADRs (`0051`–`0127`), and synced baseline resolution counts (`77`).

## [0.1.0] - 2026-11-23

### Added
- **Repository Scaffolding, Governance & CI Gates**: Initialized monorepo under `AGPL-3.0-only`, imported design specs into [`docs/design/`](./docs/design/), added ADR catalog ([`docs/adr/`](./docs/adr/)), [`ROADMAP.md`](./ROADMAP.md), [`docs/CONTRIBUTING.md`](./docs/CONTRIBUTING.md), strict `import-linter` Layer-0 boundary contracts, Golden Rule CI linters ([`tools/lint_agnosticism.py`](./tools/lint_agnosticism.py), [`tools/lint_modularity.py`](./tools/lint_modularity.py)), schema generator ([`tools/generate_types.py`](./tools/generate_types.py)), and roadmap validator ([`tools/roadmap.py`](./tools/roadmap.py)).
- **Core Agnostic Ruleset VM (`backend/app/ruleset_vm/`)**:
  - Bounded recursive-descent AST formula evaluator (`ast_evaluator.py`, zero `eval`/`exec`, deterministic step explainer).
  - Named seeded RNG streams (`rng.py`) and 7 randomizer paradigms (`randomizers.py`: `dice_formula`, `dice_pool`, `step_dice`, first-class `coin_flip` per [ADR-0132](./docs/adr/0132-first-class-coin-flip-randomizer.md), `card_deck`, `resource_wager`, and `none`).
  - Pluggable flow modes (`flow_controller.py`: `freeform`, `round_initiative`, `popcorn_spotlight`), explicit `PENDING_REACTION` / contested windows (`reaction_window.py`), event-sourced replay state machine (`vm.py`), and `MeddahModule` manifest/dormancy/RBAC registry (`module_registry.py` with `RAW` defaults).
  - Universal Composable Container & Layered Apparel/Gear Graph (`inventory_graph.py`: AST weight caps, slots, 2D grid placement/rotation, abstract load, unlimited containers with cycle detection, anatomical layering/concealment, `RAW`-gated transmog, combat `don`/`doff` outfit presets, and active aura synchronization).
  - 5-Primitive Character Creation & 5-Paradigm Advancement Engine (`advancement.py`: point-buy, standard array, random roll, package pick, lifepath chains; level-up tiers, XP store, skill usage ticks, playbook triggers, diegetic training; deterministic `CHARACTER_ADVANCED` replay event).
- **Deterministic Layer-0 MUD Parser, Social DSL & Diegetic Comms (`backend/app/mud_parser/`)**:
  - Sub-5ms Two-Tier command lexer & social DSL (`social_dsl.py`) with prosody/emphasis parsing, mixed action+speech pose interleaving (target `**you**` views & TTS/Narrator split), non-interrupting `whisper` eavesdropping, and `1–2` hop `shout` acoustic propagation.
  - 64 parameterized 3-perspective social emotes with semantic valence tagging (`social_emote_library.py`).
  - Ruleset-grounded diegetic languages (`diegetic_languages.py`: 3-tier fluency wire scrubbing, SHA-256 phonetic ciphers, shared dialect families, universal translator, dual-layer secret cants) and 6 communication medium topologies (`diegetic_comms.py`: tuned frequencies with 3-tier `ChannelPresetRegistry`, mental links, resource-gated artifacts, persistent networks, location-scoped broadcasts, async couriers, `#sealed_helmet` zero bleed, optional `VoiceModulatorProfile`, and acoustic/condition gating).
  - Host-created custom emotes, 4-step sandboxed declarative `ECA` custom MUD commands, RBAC gating, non-blocking channeling countdowns, live `/` autocomplete, and player shorthand aliases (`custom_commands.py`).
- **JSON Schemas & 7 Conformance Ruleset Fixtures**:
  - Generated 9 authoritative JSON Schemas in [`schemas/`](./schemas/) (`advancement`, `comms_medium`, `custom_command`, `custom_emote`, `event`, `inventory`, `language`, `manifest`, `ruleset`).
  - Bundled 3 Showcase Rulesets (`classic_d20_fantasy`, `grimdark_d100_investigative`, `narrative_2d6_clocks`), 4 minimal Conformance Fixtures (`dice_pool_successes`, `step_symbol_dice`, `resource_wager_card_draw`, `rules_light_narrative`), 14 golden replay-verified scenarios, [`assets/PROVENANCE.md`](./assets/PROVENANCE.md), and full unit/property/conformance/`<5ms` perf suites (60 `zero_ai` tests passing).
