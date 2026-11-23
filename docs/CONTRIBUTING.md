# Contributing to Meddah

Thank you for your interest in contributing to **Meddah: The Universal Story Engine**!

Before making changes, please review the architectural principles and engineering standards in [`docs/design/development_workflow_and_repository_standards.md`](./design/development_workflow_and_repository_standards.md).

## Core Invariants Every Change Must Respect

1. **Zero-Assumption Agnosticism (Golden Rule #1)**: Engine core (`backend/app/ruleset_vm/`) and modular systems must never hardcode game-specific terms (e.g., `"HP"`, `"AC"`, `"d20"`, `"Spell Slot"`). Mechanics come declaratively from `.rpgrules` schemas.
2. **100% Deterministic & Zero-AI Usability (Golden Rule #2)**: Every feature must work end-to-end with `AI_PROVIDER=none` (`0` LLM calls) and pass the `pytest -m zero_ai` suite.
3. **Modularity & Dormancy (§1.0 / Golden Rule #4)**: Optional subsystems register a `MeddahModule` manifest, stay `dormant` when required primitives are absent, ship with Rules as Written (RAW) defaults for outcome-altering levers, and pass `enable -> play -> disable -> enable` replay-hash checks.
4. **Pure Event Application & Seeded RNG**: Never use raw `random.*`, `time.time()`, or `datetime.now()` inside VM/event handlers; use deterministic named RNG streams (`self.rng("dice")`, etc.).

## Branching & Commit Conventions

- **Trunk Branch**: `main` must always pass CI.
- **Feature Branches**: `feat/<phase>-<short-description>`, `fix/<issue-or-subsystem>`, `docs/<topic>`.
- **Commit Messages**: Adhere strictly to Conventional Commits:
  - Types: `feat`, `fix`, `refactor`, `perf`, `test`, `docs`, `chore`, `ci`
  - Scopes: `vm`, `mud`, `storage`, `world`, `systems`, `ingestion`, `agents`, `vtt`, `multiplayer`, `media`, `safety`, `desktop`, `types`, `adr`
  - Example: `feat(vm): implement AST expression evaluator and seeded RNG streams`

## Pull Request Workflow

1. Check [`ROADMAP.md`](../ROADMAP.md) for current phase scope and [`docs/design/`](./design/) for authoritative subsystem specs.
2. Update or create an ADR in [`docs/adr/`](./adr/) if your PR modifies an architectural decision (never silently delete or overwrite an accepted decision).
3. Ensure `.env` files or secrets are never staged or committed (`.env.example` only).
4. Open a PR against `main` using the repository PR template and verify all CI gates are green.

## License

By contributing to Meddah, you agree that your code contributions will be licensed under the **GNU Affero General Public License v3.0 (`AGPL-3.0-only`)** as specified in [`LICENSE`](../LICENSE).
