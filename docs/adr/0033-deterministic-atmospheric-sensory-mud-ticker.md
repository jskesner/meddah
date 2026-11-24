# 0033. Deterministic Atmospheric & Sensory MUD Ticker

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Architectural Decision #33 (`docs/design/system_design_specification.md`)

## Context & Problem Statement
Architectural design constraint and domain resolution for **Deterministic Atmospheric & Sensory MUD Ticker** in Meddah: The Universal Story Engine.

## Decision
**Zero-LLM Scheduled Multi-Layer Sensory Emotes (`ambient_ticker.py`)**: **(1) Varying Jittered Schedules & Anti-Spam Gating** (the deterministic Python MUD engine runs per-room background timers on customizable jittered intervals—e.g., `35s–75s` in a bustling market vs. `120s–240s` in a quiet tomb—automatically pausing during active combat turns, dialogue streaming, or user typing, with client frequency presets `Frequent / Normal / Rare / Off`); **(2) 5 Composable Context-Filtered Sensory Pools** (**[a] Room & 1-Hop Neighbor Bleed Micro-Sensory Pool** [*smell of fresh-baked bread from an oven, brine-and-offal stench of a fishmarket, crackle of a hearth*], **[b] Settlement / District Crowd & Time-of-Day Pool** [*bustling crowd jostling past, a merchant's hawking cry at midday, a stray dog barking in a midnight alley*], **[c] Weather, Season & Exposure-Aware Pool** [*rain pattering on slate roofs, autumn wind swirling dry leaves, oppressive summer heat shimmer*], **[d] Living Entity / Companion Idle Emote Pool** [*the blacksmith pumping bellows, a companion sharpening a blade or flipping a coin*], and **[e] Stratum / Vessel / Facility Hum Pool** [*cavern water drips, starship reactor thrum, distant arcane hum*]); and **(3) Dynamic Variable Interpolation & Live Authoring** (messages interpolate present NPCs/items/weather, never repeat consecutively via an LRU ring buffer, are auto-seeded during World/Town/Room generation, and are 100% editable in the Live GM & Solo Room/Town Builder).

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Enforced by phase DoD suites (`pytest -m zero_ai`, `tools/lint_agnosticism.py`, `tools/lint_modularity.py`, and `import-linter`) as implementation lands.
