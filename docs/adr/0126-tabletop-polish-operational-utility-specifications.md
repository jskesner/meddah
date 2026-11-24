# 0126. Tabletop Polish & Operational Utility Specifications (Handouts/Codex, Commerce/Trading, VTT Pings/Annotations, `.rpgcharacter`, Chronicle Export, Hotbar/Keybindings & Onboarding Wizard)

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Grill-Me Resolution #76 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Tabletop Polish & Operational Utility Specifications (Handouts/Codex, Commerce/Trading, VTT Pings/Annotations, `.rpgcharacter`, Chronicle Export, Hotbar/Keybindings & Onboarding Wizard)**.

## Decision
Fleshed out 6 previously brief utility areas across the technical specification volumes:
    - **Handouts, 3-Tier Journals & Discovery-Gated Lore Codex ([Vol 3, §1.5 item 2.5](./tech_spec_03_world_cosmology_and_society.md))**: Multi-format cipher/image/audio Handouts with server-enforced per-seat visibility, Private/Shared/GM Journals, and a fog-of-war Lore Codex & Bestiary Knowledge log.
    - **In-Game Commerce, Merchant Transactions & Atomic Player-to-Player Trading ([Vol 5, §1.16 item 5](./tech_spec_05_gameplay_systems_and_anatomy.md))**: `commerce_and_trade.py` handling ruleset currency conversion, shop buy/sell spreads, reputation/haggling checks, buyback tabs, and atomic event-sourced two-sided `> trade @player` sessions preventing item duplication.
    - **VTT Table-Coordination Utilities ([Vol 4, §1.9 item 7.5](./tech_spec_04_multiplayer_ui_and_vtt.md))**: Color-coded radial Map Pings & GM Camera Pull, ephemeral/GM-layer Freehand Annotations & Sticky Pins, and the adaptive Turn/Initiative Tracker Strip.
    - **Portable Character Packages (`.rpgcharacter`), Offline Sheet Printing & First-Run Campaign Setup Wizard ([Vol 1, §1.1 item 4](./tech_spec_01_core_vm_and_ingestion.md) & [Vol 4, §1.7 item 13](./tech_spec_04_multiplayer_ui_and_vtt.md))**: Signed `.rpgcharacter` archives with ruleset-hash compatibility & Host approval queues, printable Markdown/HTML/PDF character sheets, and a 5-step deterministic First-Run Onboarding Wizard.
    - **MUD Log Search, Filtering, Bookmarks & Campaign Chronicle Export ([Vol 4, §1.7 item 11](./tech_spec_04_multiplayer_ui_and_vtt.md))**: Channel tabs, SQLite FTS5 cross-session search, pinned moment bookmarks, and Fog-of-War-filtered Markdown/HTML/PDF/JSONL Chronicle exports.
    - **Pinned Quick-Action Hotbar, Remappable Keybindings & Workspace Layout Presets ([Vol 4, §1.7 item 12](./tech_spec_04_multiplayer_ui_and_vtt.md))**: `1–9`/`F1–F12` drag-and-drop hotbar, client-local remappable shortcuts with accessibility defaults, and saveable split-pane layout presets.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
