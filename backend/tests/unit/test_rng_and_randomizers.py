"""Unit tests for deterministic RNG streams and all 6 VM randomizer types."""

from __future__ import annotations

import pytest

from app.ruleset_vm.blocks import DeckSpec, OutcomeTier, RandomizerSpec
from app.ruleset_vm.randomizers import resolve_randomizer
from app.ruleset_vm.rng import SceneRngRegistry


@pytest.mark.zero_ai
def test_rng_stream_isolation_and_checkpoint_replay() -> None:
    """Named streams are independent and restore identically from snapshots."""
    reg_a = SceneRngRegistry("scene-seed-alpha")
    dice_a = reg_a.stream("dice")
    loot_a = reg_a.stream("loot")

    first_two_dice = [dice_a.randint(1, 20), dice_a.randint(1, 20)]
    checkpoint = reg_a.snapshots()

    # Drawing from loot stream must never alter subsequent dice rolls
    _ = [loot_a.randint(1, 100) for _ in range(5)]
    next_dice = [dice_a.randint(1, 20) for _ in range(4)]

    reg_b = SceneRngRegistry("scene-seed-alpha", initial_states=checkpoint)
    dice_b = reg_b.stream("dice")
    assert [dice_b.randint(1, 20) for _ in range(4)] == next_dice

    reg_fresh = SceneRngRegistry("scene-seed-alpha")
    assert [reg_fresh.stream("dice").randint(1, 20) for _ in range(2)] == first_two_dice


@pytest.mark.zero_ai
def test_dice_formula_keep_explode_and_tiers() -> None:
    """dice_formula supports NdS, keep-highest, keep-lowest, exploding dice, and tiers."""
    rng = SceneRngRegistry("dice-test-seed").stream("dice")
    spec = RandomizerSpec(kind="dice_formula", formula="4d6kh3 + 2")
    tiers = (
        OutcomeTier(tier_id="strong", label="Strong", condition="@roll.total >= 10"),
        OutcomeTier(tier_id="miss", label="Miss", condition="true"),
    )
    res, _ = resolve_randomizer(spec, rng, {}, modifier_value=1, tiers=tiers)
    assert len(res.raw_rolls) == 4
    assert len(res.kept_rolls) == 3
    assert res.kept_rolls == tuple(sorted(res.raw_rolls, reverse=True)[:3])
    assert res.total == sum(res.kept_rolls) + 3
    assert res.tier_id in {"strong", "miss"}

    adv_spec = RandomizerSpec(kind="dice_formula", formula="2d20kh1")
    adv_res, _ = resolve_randomizer(adv_spec, rng, {})
    assert len(adv_res.raw_rolls) == 2
    assert adv_res.kept_rolls == (max(adv_res.raw_rolls),)

    exp_spec = RandomizerSpec(kind="dice_formula", formula="1d4!")
    exp_res, _ = resolve_randomizer(exp_spec, rng, {})
    assert exp_res.total >= 1


@pytest.mark.zero_ai
def test_dice_pool_hits_and_strict_glitch_ratio() -> None:
    """dice_pool counts hits >= threshold and flags glitch strictly when ones > 50%."""
    found_glitch = False
    found_non_glitch = False
    rng = SceneRngRegistry("pool-glitch-test").stream("dice")
    for _ in range(1000):
        spec = RandomizerSpec(
            kind="dice_pool",
            pool_size_formula="4",
            die_sides=6,
            success_threshold=5,
            glitch_face=1,
            glitch_ratio=0.5,
        )
        res, _ = resolve_randomizer(spec, rng, {})
        ones = sum(1 for r in res.raw_rolls if r == 1)
        assert res.hits == sum(1 for r in res.raw_rolls if r >= 5)
        if ones == 2:
            assert res.is_glitch is False
            found_non_glitch = True
        elif ones >= 3:
            assert res.is_glitch is True
            found_glitch = True
        if found_glitch and found_non_glitch:
            break

    assert found_glitch
    assert found_non_glitch


@pytest.mark.zero_ai
def test_step_dice_symbols_card_deck_wager_and_none() -> None:
    """Verify step_dice, card_deck without replacement + reshuffle, resource_wager, and none."""
    rng = SceneRngRegistry("multi-randomizer").stream("dice")

    step_spec = RandomizerSpec(
        kind="step_dice",
        step_die_formula="@self.trait_die",
        wild_die_sides=6,
        explode=True,
        face_symbols={1: ("miss",), 6: ("triumph", "success")},
    )
    step_res, _ = resolve_randomizer(step_spec, rng, {"@self": {"trait_die": 8}})
    assert step_res.kind == "step_dice"
    assert len(step_res.raw_rolls) >= 2
    assert step_res.total >= 1

    deck_spec = DeckSpec(
        deck_id="fate_deck",
        label="Fate Deck",
        cards=("ace", "two", "three", "four"),
        card_values={"ace": 1, "two": 2, "three": 3, "four": 4},
    )
    card_spec = RandomizerSpec(
        kind="card_deck",
        deck_id="fate_deck",
        draw_count=2,
        reshuffle_on_empty=True,
    )
    draw_1, decks = resolve_randomizer(
        card_spec,
        rng,
        {},
        deck_specs={"fate_deck": deck_spec},
        deck_states={},
    )
    assert len(draw_1.drawn_cards) == 2
    assert len(decks["fate_deck"].draw_pile) == 2

    # Second draw empties draw_pile; third draw triggers deterministic reshuffle
    draw_2, decks = resolve_randomizer(
        card_spec,
        rng,
        {},
        deck_specs={"fate_deck": deck_spec},
        deck_states=decks,
    )
    assert len(draw_2.drawn_cards) == 2
    assert set(draw_1.drawn_cards) | set(draw_2.drawn_cards) == {"ace", "two", "three", "four"}

    draw_3, decks = resolve_randomizer(
        card_spec,
        rng,
        {},
        deck_specs={"fate_deck": deck_spec},
        deck_states=decks,
    )
    assert len(draw_3.drawn_cards) == 2
    assert len(decks["fate_deck"].draw_pile) == 2

    pos_before = rng.position
    wager_res, _ = resolve_randomizer(
        RandomizerSpec(kind="resource_wager", base_value=2),
        rng,
        {},
        modifier_value=3,
        wager_bonus=4,
    )
    assert wager_res.total == 9
    assert rng.position == pos_before

    none_res, _ = resolve_randomizer(
        RandomizerSpec(kind="none", base_value=1),
        rng,
        {},
        modifier_value=2,
    )
    assert none_res.total == 3
    assert rng.position == pos_before
