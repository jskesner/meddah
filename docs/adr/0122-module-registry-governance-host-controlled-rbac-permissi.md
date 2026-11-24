# 0122. Module Registry Governance — Host-Controlled RBAC Permissions, Isolated Sandbox Test Instances & Safe-Boundary Activation (`module_registry.py` — Phase 1 & Phase 6 [MVP], §1.0)

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Grill-Me Resolution #72 (`docs/design/technical_specification_and_plan.md` §2.1)

## Context & Problem Statement
Operational refinement and scope resolution for **Module Registry Governance — Host-Controlled RBAC Permissions, Isolated Sandbox Test Instances & Safe-Boundary Activation (`module_registry.py` — Phase 1 & Phase 6 [MVP], §1.0)**.

## Decision
- **Host-Controlled Module Toggling Permission (`can_toggle_campaign_modules`)**: In Multiplayer, **Guest Players cannot toggle campaign or session modules by default** (they may only adjust their own `player_local` presentation/audio/accessibility settings). The **Host (`is_server_admin / host`)** controls module-toggling permissions and can selectively enable `can_toggle_campaign_modules` for **GM / Co-GM** seats.
   - **Host-Controlled Module Toggling Permission (`can_toggle_campaign_modules`)**: In Multiplayer, **Guest Players cannot toggle campaign or session modules by default** (they may only adjust their own `player_local` presentation/audio/accessibility settings). The **Host (`is_server_admin / host`)** controls module-toggling permissions and can selectively enable `can_toggle_campaign_modules` for **GM / Co-GM** seats.
   - **Zero-Disruption Isolated Sandbox Test Instance**: The Module Manager provides a **`[Test in Isolated Sandbox Instance]`** button that launches a private, ephemeral Copy-on-Write clone of the campaign snapshot so the Host or authorized GM can test-drive module combinations against sample rolls/encounters without pausing, mutating, or disrupting an active multiplayer session.
   - **Confirmed Safe-Boundary Live Activation**: Applying module changes to a live campaign requires an explicit Host/GM confirmation dialog, creates an automatic pre-change checkpoint, and queues the audited `MODULE_OVERRIDE` event to activate at a safe boundary (`Next Scene / Rest / Session Boundary` by default, or `End of Current Atomic Turn / Resolution Step` when explicitly selected).

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Verified via phase acceptance tests, determinism suites, and design-doc traceability.
