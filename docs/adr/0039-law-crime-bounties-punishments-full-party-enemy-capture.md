# 0039. Law, Crime, Bounties, Punishments & Full-Party Enemy Capture

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Architectural Decision #39 (`docs/design/system_design_specification.md`)

## Context & Problem Statement
Architectural design constraint and domain resolution for **Law, Crime, Bounties, Punishments & Full-Party Enemy Capture** in Meddah: The Universal Story Engine.

## Decision
**100% Ruleset-Grounded Justice & Captivity Engine (`law_and_justice.py` & `captivity_and_breakout.py`)**: **(1) Zero Telepathic Guards & Strict Witness/LoS Detection** (unwitnessed crimes out of 2.5D Ray-Cast LoS/hearing never auto-flag bounties; supports **Disguises / Masked Personas** and a **Witness Reaction Window**); **(2) Jurisdiction-Scoped Legal Codes (`JurisdictionLawBlock`)**; **(3) 5-Option Guard Confrontation Flow** (`Pay Fine`, `Bribe`, `Pull Rank / Persuade`, `Flee / Chase`, or `Fight`); **(4) Non-Game-Over Punishment, Trials & Playable Prison Breaks** (**Interactive Trials**, **Evidence Locker Gear Recovery**, **Downtime Sentence Time-Skips**, or **Playable `Scale 4` Prison Breaks**); and **(5) Full-Party Capture by Enemy Factions / Monsters ("Fail-Forward Defeat")** (reuses the exact same **Jailbreak & Captivity Engine** when a party is defeated/captured by bandits, slavers, cultists, enemy ships/trains, or monsters with `defeat_disposition: "capture_alive"`—waking up in the **Enemy Lair/Stockade/Ship Brig/Web Cocoons** with party gear intact in the **Captor Armory (`ContainerNode`)**, concealed-item smuggle checks, split-cell/interrogation room RP, Familiar/Pet/Patron aid, Gladiator/Labor Yard scenes, or switching to **Stationed Home-Base AI Companions ["The B-Team"]** to stage an outside-in rescue!).

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Enforced by phase DoD suites (`pytest -m zero_ai`, `tools/lint_agnosticism.py`, `tools/lint_modularity.py`, and `import-linter`) as implementation lands.
