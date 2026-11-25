# 0121. Vitality Topologies — Per-Archetype/Entity Topology Overrides & Proportional Reversible Mid-Campaign Mapping (`HitLocationTopologyBlock` — Phase 10 [Post-MVP], Volume 5 §1.29)

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Design Resolution #71 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Vitality Topologies — Per-Archetype/Entity Topology Overrides & Proportional Reversible Mid-Campaign Mapping (`HitLocationTopologyBlock` — Phase 10 [Post-MVP], Volume 5 §1.29)**.

## Decision
- **3-Tier Per-Archetype & Per-Entity Vitality Topology Overrides**: Just like loot generation profiles, `vitality_topology` resolves via **`Individual Entity Override -> Creature Archetype Definition -> Campaign Default`**, allowing swarm/minion enemies to use fast `"monolithic"` vitality, Player Characters to use `"composite_dual"` or `"monolithic"`, and colossal dragons, mechs, or multi-part bosses to use `"independent_locations"` with targetable limbs/subsystems in the exact same encounter.
   - **3-Tier Per-Archetype & Per-Entity Vitality Topology Overrides**: Just like loot generation profiles, `vitality_topology` resolves via **`Individual Entity Override -> Creature Archetype Definition -> Campaign Default`**, allowing swarm/minion enemies to use fast `"monolithic"` vitality, Player Characters to use `"composite_dual"` or `"monolithic"`, and colossal dragons, mechs, or multi-part bosses to use `"independent_locations"` with targetable limbs/subsystems in the exact same encounter.
   - **Proportional Reversible Vitality Mapping on Module Toggle**: Toggling `hit_locations` on/off or switching topologies mid-campaign preserves raw vitality events in the append-only log while mapping current health percentages proportionally between `vitality.total` and `vitality.locations[location_id]` so no character wounds are lost or artificially healed.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
