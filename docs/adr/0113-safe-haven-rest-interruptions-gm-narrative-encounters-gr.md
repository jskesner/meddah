# 0113. Safe Haven Rest Interruptions, GM Narrative Encounters & Granular Urban Danger Zoning (`safety_rating` — Sections 1.13 & 1.24)

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Grill-Me Resolution #63 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Safe Haven Rest Interruptions, GM Narrative Encounters & Granular Urban Danger Zoning (`safety_rating` — Sections 1.13 & 1.24)**.

## Decision
- **Safe Haven Is Not Invulnerable Immunity**: Nominal "Safe Haven" designation (`safety_rating: "safe_haven"`) suppresses ambient, passive wandering monster rolls, but GMs (Human GM via Director Dock, AI GM via dramatic pacing / faction clocks / bounty callbacks, or Solo Director) always retain authoritative agency to initiate events, ambushes, and encounters anywhere—including nominally "safe" tavern taprooms, inns, or private residences (e.g. barroom brawls, midnight assassination attempts, stealth thief break-ins, corrupt guard raids, or arson).
   - **Safe Haven Is Not Invulnerable Immunity**: Nominal "Safe Haven" designation (`safety_rating: "safe_haven"`) suppresses ambient, passive wandering monster rolls, but GMs (Human GM via Director Dock, AI GM via dramatic pacing / faction clocks / bounty callbacks, or Solo Director) always retain authoritative agency to initiate events, ambushes, and encounters anywhere—including nominally "safe" tavern taprooms, inns, or private residences (e.g. barroom brawls, midnight assassination attempts, stealth thief break-ins, corrupt guard raids, or arson).
   - **Rest Interruption & Partial Recovery Flow**: Mid-rest interruptions pause the rest session rather than wiping progress. The Ruleset VM evaluates elapsed rest time against the active `.rpgrules` `RestTierBlock` hierarchy: if the party completed enough time for a lower rest tier (e.g. *Short Rest / Breather*), partial recovery is deterministically locked in before combat begins. Sleeping characters evaluate armor/equipment readiness strictly per ruleset mechanics (unarmored bed attire, weapons on nightstands, `#asleep` condition until awakened). Following encounter resolution, the party can click `[Resume Rest]`, relocate to a new safehouse, or pursue leads.
   - **Three-Tier Settlement & Urban Danger Zoning (`safety_rating`)**: Settlements and cities are not monolithic havens; room nodes carry granular danger ratings:
     1. `safety_rating: "safe_haven"`: Secure private sanctuaries (locked inn suites, apartments, guildhalls, strongholds) with 0% ambient monster wanderers; long rests require no watch roster; GM/faction targeted events remain active.
     2. `safety_rating: "settlement_public"`: Public urban venues (tavern taprooms, bazaars, town squares, temple plazas) running low-lethality **Urban Public Social & Disturbance Pools** (pickpockets, barroom brawls, criers, guard patrols, drunkards).
     3. `safety_rating: "settlement_hostile"`: Dangerous urban underbellies (Lowtown slums, smuggler docks, crime syndicate turf, sewers, undercity ruins, riot zones) where **Active Combat Encounter Tables and Tension Pools run continuously**; resting in these nodes defaults to **Mode A (Wilderness Camp Rules)** requiring watch shifts, barricades, and ambush checks unless a secure safehouse is established.
   - **100% Ruleset Agnostic & Admin Configurable**: All recovery formulas, sleep armor rules, and status effects bind to `.rpgrules`; all encounter chances, district danger multipliers, and pacing cooldowns are configurable by server admins in `server.toml` and GMs in the Live Settlement Studio.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
