"""Hypothesis property-based tests for AST evaluator, RNG streams, dice bounds & replay."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.ruleset_vm import (
    ActionBlock,
    EffectSpec,
    EntityState,
    OutcomeTier,
    PackageManifest,
    RandomizerSpec,
    ResolutionMechanicBlock,
    ResourcePoolBlock,
    RulesetSchema,
    evaluate_formula,
    execute_action,
    initialize_scene_state,
    replay_events,
    resolve_randomizer,
    state_hash,
)
from app.ruleset_vm.rng import DeterministicRngStream


@pytest.mark.zero_ai
@given(
    a=st.integers(min_value=-10_000, max_value=10_000),
    b=st.integers(min_value=-10_000, max_value=10_000),
    c=st.integers(min_value=-100, max_value=100),
)
def test_ast_arithmetic_matches_python_semantics(a: int, b: int, c: int) -> None:
    """AST evaluator arithmetic matches exact Python integer arithmetic."""
    ctx = {"@self": {"a": a, "b": b, "c": c}}
    assert evaluate_formula("(@self.a + @self.b) * @self.c", ctx) == (a + b) * c
    assert evaluate_formula("@self.a >= @self.b ? @self.a : @self.b", ctx) == max(a, b)


@pytest.mark.zero_ai
@given(
    seed=st.text(min_size=1, max_size=24),
    stream_name=st.text(min_size=1, max_size=16),
    count=st.integers(min_value=1, max_value=20),
    sides=st.integers(min_value=2, max_value=100),
    mod=st.integers(min_value=-50, max_value=50),
)
def test_dice_formula_bounds_and_seed_determinism(
    seed: str,
    stream_name: str,
    count: int,
    sides: int,
    mod: int,
) -> None:
    """Dice totals stay within [count + mod, count * sides + mod] and replay identically."""
    spec = RandomizerSpec(kind="dice_formula", formula=f"{count}d{sides}")
    rng_1 = DeterministicRngStream(seed=seed, stream_name=stream_name)
    rng_2 = DeterministicRngStream(seed=seed, stream_name=stream_name)

    res_1, _ = resolve_randomizer(spec, rng_1, {}, modifier_value=mod)
    res_2, _ = resolve_randomizer(spec, rng_2, {}, modifier_value=mod)

    assert res_1 == res_2
    assert len(res_1.raw_rolls) == count
    assert count + mod <= res_1.total <= count * sides + mod


@pytest.mark.zero_ai
@given(
    seed=st.text(min_size=1, max_size=16),
    steps=st.integers(min_value=1, max_value=15),
)
def test_event_replay_hash_always_matches_live_execution(seed: str, steps: int) -> None:
    """Replaying any sequence of VM actions yields the identical SHA-256 SceneState hash."""
    ruleset = RulesetSchema(
        manifest=PackageManifest(
            package_type="ruleset",
            package_id="prop_replay",
            name="Property Replay",
            version="0.1.0",
        ),
        resource_pools={
            "vitality": ResourcePoolBlock(pool_id="vitality", label="Vitality", default_current=100)
        },
        resolutions={
            "roll_1d6": ResolutionMechanicBlock(
                mech_id="roll_1d6",
                label="Roll 1d6",
                randomizer=RandomizerSpec(kind="dice_formula", formula="1d6"),
                tiers=(
                    OutcomeTier(
                        tier_id="tick",
                        label="Tick",
                        condition="true",
                        effects=(
                            EffectSpec(
                                kind="modify_pool",
                                target_scope="self",
                                target_key="vitality",
                                formula="-@roll.total",
                            ),
                        ),
                    ),
                ),
            )
        },
        actions={"drain": ActionBlock(action_id="drain", label="Drain", resolution_id="roll_1d6")},
    )
    initial = initialize_scene_state(
        ruleset,
        "prop_scene",
        [EntityState(entity_id="pc", name="Runner")],
        scene_seed=seed,
    )

    cur = initial
    all_events = []
    for _ in range(steps):
        res = execute_action(ruleset, cur, "pc", "drain")
        cur = res.state
        all_events.extend(res.events)

    replayed = replay_events(ruleset, initial, all_events)
    assert state_hash(replayed) == state_hash(cur)


@pytest.mark.zero_ai
@given(
    seed=st.text(min_size=1, max_size=24),
    count=st.integers(min_value=1, max_value=30),
)
def test_coin_flip_counts_bounds_and_determinism(seed: str, count: int) -> None:
    """Pooled coin flips preserve total coin count and replay deterministically."""
    spec = RandomizerSpec(
        kind="coin_flip",
        pool_size_formula=str(count),
        coin_heads_label="Crown",
        coin_tails_label="Skull",
    )
    rng_1 = DeterministicRngStream(seed=seed, stream_name="coins")
    rng_2 = DeterministicRngStream(seed=seed, stream_name="coins")

    res_1, _ = resolve_randomizer(spec, rng_1, {})
    res_2, _ = resolve_randomizer(spec, rng_2, {})

    assert res_1 == res_2
    assert res_1.heads_count is not None
    assert res_1.tails_count is not None
    assert 0 <= res_1.heads_count <= count
    assert res_1.heads_count + res_1.tails_count == count
    assert len(res_1.symbols) == count
