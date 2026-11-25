"""Hypothesis property tests for Alternate Form transformations and pool spillover (ADR-0133)."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.ruleset_vm import (
    ActionBlock,
    EffectSpec,
    EntityState,
    FormBlock,
    FormPoolSpec,
    OutcomeTier,
    PackageManifest,
    PropertyBlock,
    RandomizerSpec,
    ResolutionMechanicBlock,
    ResourcePoolBlock,
    RulesetSchema,
    compute_entity_view,
    execute_action,
    initialize_scene_state,
    replay_events,
    revert_form,
    shift_into_form,
    state_hash,
)


def _prop_form_ruleset(damage_amount: int) -> RulesetSchema:
    return RulesetSchema(
        manifest=PackageManifest(
            package_type="ruleset",
            package_id="prop_forms",
            name="Property Forms",
            version="0.1.0",
        ),
        properties={
            "might": PropertyBlock(prop_id="might", label="Might", default_value=10),
            "cognition": PropertyBlock(prop_id="cognition", label="Cognition", default_value=12),
        },
        resource_pools={
            "vitality": ResourcePoolBlock(
                pool_id="vitality",
                label="Vitality",
                default_current=20,
                max_formula="200",
                min_value=0,
            ),
        },
        resolutions={
            "flat_dmg": ResolutionMechanicBlock(
                mech_id="flat_dmg",
                label="Flat Damage",
                randomizer=RandomizerSpec(kind="none", base_value=0),
                tiers=(
                    OutcomeTier(
                        tier_id="hit",
                        label="Hit",
                        condition="true",
                        effects=(
                            EffectSpec(
                                kind="modify_pool",
                                target_scope="target",
                                target_key="vitality",
                                formula=f"-{damage_amount}",
                            ),
                        ),
                    ),
                ),
            ),
        },
        actions={
            "deal_dmg": ActionBlock(
                action_id="deal_dmg",
                label="Deal Damage",
                category="action",
                resolution_id="flat_dmg",
                requires_target=True,
            ),
        },
        forms={
            "beast": FormBlock(
                form_id="beast",
                label="Beast Form",
                property_mode="replace_subset",
                property_values={"might": 19},
                pool_policies={
                    "vitality": FormPoolSpec(
                        mode="separate_form_pool",
                        initial_formula="15",
                        max_formula="15",
                        overflow_to_base=True,
                        auto_revert_on_zero=True,
                    ),
                },
            ),
        },
    )


@pytest.mark.zero_ai
@settings(max_examples=40)
@given(
    might=st.integers(min_value=3, max_value=20),
    cognition=st.integers(min_value=3, max_value=20),
    vitality=st.integers(min_value=1, max_value=100),
)
def test_shift_and_revert_preserves_base_state_when_no_costs(
    might: int,
    cognition: int,
    vitality: int,
) -> None:
    """Zero-cost shift followed by revert preserves base_properties & base pools identically."""
    rs = _prop_form_ruleset(0)
    hero = EntityState(
        entity_id="pc_1",
        name="Hero",
        base_properties={"might": might, "cognition": cognition},
        pools={"vitality": vitality},
    )
    scene = initialize_scene_state(rs, "prop_scene", [hero])

    shifted = shift_into_form(rs, scene, "pc_1", "beast")
    assert compute_entity_view(rs, shifted.state.entities["pc_1"]).properties["might"] == 19
    assert (
        compute_entity_view(rs, shifted.state.entities["pc_1"]).properties["cognition"] == cognition
    )

    reverted = revert_form(rs, shifted.state, "pc_1")
    end_ent = reverted.state.entities["pc_1"]
    assert end_ent.active_form is None
    assert end_ent.base_properties == hero.base_properties
    assert end_ent.pools == scene.entities["pc_1"].pools

    replayed = replay_events(rs, scene, [*shifted.events, *reverted.events])
    assert state_hash(replayed) == state_hash(reverted.state)


@pytest.mark.zero_ai
@settings(max_examples=50)
@given(
    base_vit=st.integers(min_value=5, max_value=80),
    dmg=st.integers(min_value=0, max_value=120),
)
def test_separate_form_pool_overflow_damage_conservation_and_replay(
    base_vit: int,
    dmg: int,
) -> None:
    """Form vitality (15) + base vitality strictly conserve damage overflow and replay hashes."""
    rs = _prop_form_ruleset(dmg)
    hero = EntityState(entity_id="pc_1", name="Hero", pools={"vitality": base_vit})
    foe = EntityState(entity_id="foe_1", name="Foe", pools={"vitality": 50})
    initial = initialize_scene_state(rs, "overflow_scene", [hero, foe])

    shifted = shift_into_form(rs, initial, "pc_1", "beast")
    res = execute_action(rs, shifted.state, "foe_1", "deal_dmg", target_id="pc_1")
    end_ent = res.state.entities["pc_1"]

    end_form_vit = end_ent.active_form.form_pools.get("vitality", 0) if end_ent.active_form else 0
    end_base_vit = end_ent.pools["vitality"]

    expected_total = max(0, (15 + base_vit) - dmg)
    assert end_form_vit + end_base_vit == expected_total
    if dmg >= 15:
        assert end_ent.active_form is None

    replayed = replay_events(rs, initial, [*shifted.events, *res.events])
    assert state_hash(replayed) == state_hash(res.state)
