# 0037. Permanent Pets, Familiars, Mounts, Drones & Minions

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Architectural Decision #37 (`docs/design/system_design_specification.md`)

## Context & Problem Statement
Architectural design constraint and domain resolution for **Permanent Pets, Familiars, Mounts, Drones & Minions** in Meddah: The Universal Story Engine.

## Decision
**5-Category Ruleset-Grounded Retinue Engine (`pets_mounts_minions.py` & `retinue_panel/`)**: **(1) Five Retinue Archetypes** (**[a] Narrative Mascots/Pets** [sheltered from combat AoEs by default + ambient emotes & camp interactions], **[b] Familiars, Spirit Totems & Recon Drones** [perched/pocketed vs. deployed states, remote Line-of-Sight/FoW scouting link, and ruleset resummon/repair], **[c] Bonded Combat Companions** [Ranger beasts, Eidolons, Battle Automatons, Cyber-Hounds that scale with owner progression and equip barding/modules], **[d] Permanent Mounts & Steeds** [composite mounted token merging, `Z+1` aerial/special movement, saddlebag container offloading, and `Hitched Outside Dungeon` persistence], and **[e] Permanent Minions, Undead Thralls, Golems & Retainers** [ruleset control-pool caps, Individual vs. **Squad/Swarm Token Grouping** to prevent turn bloat, and town social reaction tags]); **(2) Pluggable Turn Economy & Control** (supports Owner-Action Command, Shared Initiative, or Independent Turn, toggleable between **Direct Player Control** and **Smart Stance Autopilot**); and **(3) Nested Retinue Sub-Portrait UI**.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Enforced by phase DoD suites (`pytest -m zero_ai`, `tools/lint_agnosticism.py`, `tools/lint_modularity.py`, and `import-linter`) as implementation lands.
