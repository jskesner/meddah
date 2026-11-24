# 0132. First-Class `coin_flip` Randomizer Primitive

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers
- **Related Issues / Decisions**: Decision #17 (`docs/design/system_design_specification.md`), ADR-0017, ADR-0076, Volume 1 §1.1 (`docs/design/tech_spec_01_core_vm_and_ingestion.md`), Volume 4 §1.7.5 (`docs/design/tech_spec_04_multiplayer_ui_and_vtt.md`)

## Context & Problem Statement
Volume 4 §1.7.5 already specifies **"3D Metallic Coin-Flips"** for the optional client 3D randomizer tray, and coin-pool tabletop RPGs (such as *Prince Valiant*, narrative coin-toss mechanics, and Fate/Luck flip systems) flip one or multiple coins with themed faces (*Heads/Tails*, *Sun/Moon*, *Crown/Skull*). Representing coins indirectly via `dice_pool` with `die_sides=2` conflated coins with 2-sided polyhedrals and lacked dedicated `@roll.heads`, `@roll.tails`, and customizable face labels.

## Decision
Elevate `coin_flip` to a first-class seventh `RandomizerKind` inside `backend/app/ruleset_vm/blocks.py` and `randomizers.py`:
1. **`RandomizerKind`**: Added `"coin_flip"` alongside `dice_formula`, `dice_pool`, `step_dice`, `card_deck`, `resource_wager`, and `none`.
2. **Customizable Setting-Agnostic Labels**: Added `coin_heads_label` (default `"heads"`) and `coin_tails_label` (default `"tails"`) on `RandomizerSpec`, paired with `pool_size_formula` for single or multi-coin pools.
3. **Deterministic Outcome & `@roll` Context**: Flips resolve cleanly via `rng.randint(0, 1)` on the scene's named RNG stream, populate `RollResult.heads_count`, `RollResult.tails_count`, `RollResult.symbols`, and `RollResult.total` (`heads_count + modifier`), and expose `@roll.heads`, `@roll.tails`, and `@roll.symbols` to `OutcomeTier` and `EffectSpec` formulas—giving the Phase 13 3D tray an explicit `kind="coin_flip"` hook.

## Consequences
### Positive
- Rulesets using single or pooled coin flips express them declaratively with arbitrary thematic coin faces.
- Clean 1:1 backend-to-frontend randomizer fidelity for 3D metallic coin animations (`ADR-0017`).

### Negative / Trade-offs
- Adds one additive `RandomizerKind` variant and two optional defaulted fields to `schemas/ruleset.schema.json` (strictly backward-compatible).

### Neutral
- Existing accepted ADRs `0001`–`0131` remain untouched in accordance with ADR immutability governance.

## Compliance & Verification
- Verified by unit tests (`test_coin_flip_single_pool_custom_labels_and_tiers`), Hypothesis property tests (`test_coin_flip_counts_bounds_and_determinism`), `tools/generate_types.py --check`, `pyright` strict mode, and `pytest -m zero_ai`.
