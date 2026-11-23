# 0131. Golden Rule #4: Modular, Opt-In & Dormant-Unless-Specified

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Golden Rule #4 (`docs/design/system_design_specification.md`)

## Context & Problem Statement
Non-negotiable invariant defining **Golden Rule #4: Modular, Opt-In & Dormant-Unless-Specified** across all engine layers and phases.

## Decision
Meddah is a **universal ruleset interpreter**, not a game, and it must **never invent mechanics a ruleset does not specify**.
* **Everything but the Core is a module**: Every subsystem is an independent, optional module (`MeddahModule` manifest, Technical Spec §1.0) that users can enable, disable, or customize individually or via shareable **Module Profiles**. Only the Ruleset VM, event store, deterministic parser, and module registry are non-optional.
* **Dormant unless the ruleset supplies the primitives**: A module whose required building blocks are absent is `dormant`—no commands, UI, events, prompts, or CPU cost. The engine never fabricates a fallback mechanic.
* **Ruleset-defined does not mean engine-mandated**: A Host can disable any module, even one the ruleset defines (audited `MODULE_OVERRIDE`); outcome-altering conveniences (roll fudging, rescues, safety nets) ship **off** unless a user picks them.
* **Graceful and reversible**: Disabling preserves event-sourced state, validates dependents, and unregisters all UI; re-enabling resumes exactly where play left off.

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Enforced continuously in CI via `tools/lint_agnosticism.py`, `tools/lint_modularity.py`, `import-linter`, and `pytest -m zero_ai`.
