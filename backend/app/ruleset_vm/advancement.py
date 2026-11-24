"""State-Graph Character Creation (5 Primitives) & Advancement Engine (5 Paradigms) (§1.1.4)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.ruleset_vm.ast_evaluator import ScalarValue, evaluate_formula
from app.ruleset_vm.blocks import RandomizerSpec, RulesetSchema
from app.ruleset_vm.randomizers import resolve_randomizer
from app.ruleset_vm.rng import SceneRngRegistry
from app.ruleset_vm.vm import ComputedEntityView, EntityState, VmEvent, compute_entity_view


def _empty_int_int_dict() -> dict[int, int]:
    return {}


def _empty_str_scalar_dict() -> dict[str, ScalarValue]:
    return {}


def _empty_str_float_dict() -> dict[str, int | float]:
    return {}


def _empty_str_int_dict() -> dict[str, int]:
    return {}


class PointBuyStepSpec(BaseModel):
    """Allocate a point budget across properties using custom or linear cost tables."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["point_buy_pool"] = "point_buy_pool"
    step_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    target_properties: tuple[str, ...] = Field(min_length=1)
    budget_points: int = Field(ge=0)
    base_value: int = 8
    min_score: int = 8
    max_score: int = 15
    cost_table: dict[int, int] = Field(default_factory=_empty_int_int_dict)


class StandardArrayStepSpec(BaseModel):
    """Assign a fixed multiset of values exactly once across target properties."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["array_assign"] = "array_assign"
    step_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    target_properties: tuple[str, ...] = Field(min_length=1)
    array_values: tuple[int, ...] = Field(min_length=1)


class RandomRollStepSpec(BaseModel):
    """Generate attributes via seeded Ruleset Randomizer rolls (in-order or pool-assign)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["random_roll_assign"] = "random_roll_assign"
    step_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    target_properties: tuple[str, ...] = Field(min_length=1)
    roll_spec: RandomizerSpec
    assign_mode: Literal["in_order", "pool_assign"] = "pool_assign"
    min_total_mercy: int | None = None
    max_rerolls: int = Field(default=10, ge=0)


class SubChoiceOption(BaseModel):
    """Single nested choice within a character creation package."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    option_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    property_bonuses: dict[str, int | float] = Field(default_factory=_empty_str_float_dict)
    granted_tags: tuple[str, ...] = ()
    granted_actions: tuple[str, ...] = ()


class SubChoiceSpec(BaseModel):
    """Nested pick-K sub-choice required when choosing an archetype/ancestry package."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    choice_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    pick_count: int = Field(default=1, ge=1)
    options: tuple[SubChoiceOption, ...] = Field(min_length=1)


class PackageOptionSpec(BaseModel):
    """Selectable ancestry, background, archetype, or playbook bundle."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    option_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    requires: str = "true"
    property_bonuses: dict[str, int | float] = Field(default_factory=_empty_str_float_dict)
    property_sets: dict[str, ScalarValue] = Field(default_factory=_empty_str_scalar_dict)
    granted_tags: tuple[str, ...] = ()
    granted_actions: tuple[str, ...] = ()
    sub_choices: tuple[SubChoiceSpec, ...] = ()


class PackagePickStepSpec(BaseModel):
    """Select an option from AST-gated character packages and fulfill sub-choices."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["package_pick"] = "package_pick"
    step_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    options: tuple[PackageOptionSpec, ...] = Field(min_length=1)


class LifepathEventEntry(BaseModel):
    """Single life-event outcome drawn during a lifepath career term."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    property_bonuses: dict[str, int | float] = Field(default_factory=_empty_str_float_dict)
    granted_tags: tuple[str, ...] = ()
    granted_actions: tuple[str, ...] = ()


class LifepathCareerSpec(BaseModel):
    """Career track traversed across multi-term lifepath generation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    career_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    requires: str = "true"
    survival_roll: RandomizerSpec
    survival_target: int
    promotion_roll: RandomizerSpec
    promotion_target: int
    term_property_bonuses: dict[str, int | float] = Field(default_factory=_empty_str_float_dict)
    events: tuple[LifepathEventEntry, ...] = ()
    mustering_currency_per_term: int = Field(default=0, ge=0)
    mustering_tags: tuple[str, ...] = ()


class LifepathChainStepSpec(BaseModel):
    """Iterative term-by-term lifepath career creation step."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["lifepath_chain"] = "lifepath_chain"
    step_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    careers: tuple[LifepathCareerSpec, ...] = Field(min_length=1)
    max_terms: int = Field(default=6, ge=1)


CreationStepSpec = Annotated[
    PointBuyStepSpec
    | StandardArrayStepSpec
    | RandomRollStepSpec
    | PackagePickStepSpec
    | LifepathChainStepSpec,
    Field(discriminator="kind"),
]


class CreationGraphSpec(BaseModel):
    """Complete ordered sequence of creation primitives for a ruleset."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    steps: tuple[CreationStepSpec, ...] = ()
    starting_pools: dict[str, int] = Field(default_factory=_empty_str_int_dict)


class LifepathTermOutcome(BaseModel):
    """Audit result of executing one lifepath career term."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    career_id: str
    term_number: int
    survived: bool
    promoted: bool
    event_id: str | None = None


class CreationSessionState(BaseModel):
    """Mutable-via-copy progressive state of a character being created."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    entity_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    completed_steps: tuple[str, ...] = ()
    base_properties: dict[str, ScalarValue] = Field(default_factory=_empty_str_scalar_dict)
    pools: dict[str, int] = Field(default_factory=_empty_str_int_dict)
    tags: tuple[str, ...] = ()
    granted_actions: tuple[str, ...] = ()
    pending_roll_pool: dict[str, tuple[int | float, ...]] = Field(default_factory=dict)
    lifepath_terms: int = Field(default=0, ge=0)
    lifepath_rank: int = Field(default=0, ge=0)
    lifepath_history: tuple[LifepathTermOutcome, ...] = ()


def _session_to_entity(session: CreationSessionState) -> EntityState:
    return EntityState(
        entity_id=session.entity_id,
        name=session.name,
        base_properties=dict(session.base_properties),
        pools=dict(session.pools),
        tags=session.tags,
        granted_actions=session.granted_actions,
    )


def _apply_bonuses(
    props: dict[str, ScalarValue],
    bonuses: Mapping[str, int | float],
) -> None:
    for key, delta in sorted(bonuses.items()):
        cur = props.get(key, 0)
        if isinstance(cur, (int, float)) and not isinstance(cur, bool):
            props[key] = cur + delta
        else:
            props[key] = delta


def start_creation_session(
    graph: CreationGraphSpec,
    ruleset: RulesetSchema,
    *,
    entity_id: str,
    name: str,
) -> CreationSessionState:
    """Initialize a CreationSessionState prefilled with ruleset defaults and starting pools."""
    props: dict[str, ScalarValue] = {
        pid: prop.default_value for pid, prop in ruleset.properties.items()
    }
    pools: dict[str, int] = dict(graph.starting_pools)
    for pool_id, pool_def in sorted(ruleset.resource_pools.items()):
        if pool_id not in pools:
            if isinstance(pool_def.default_current, int):
                pools[pool_id] = pool_def.default_current
            else:
                pools[pool_id] = 0
    return CreationSessionState(
        entity_id=entity_id,
        name=name,
        base_properties=props,
        pools=pools,
    )


def _mark_completed(completed: tuple[str, ...], step_id: str) -> tuple[str, ...]:
    if step_id in completed:
        return completed
    return (*completed, step_id)


def apply_point_buy(
    session: CreationSessionState,
    step: PointBuyStepSpec,
    allocations: Mapping[str, int],
) -> CreationSessionState:
    """Validate and apply a point_buy_pool allocation onto CreationSessionState."""
    if set(allocations.keys()) != set(step.target_properties):
        raise ValueError(
            f"Point-buy keys {sorted(allocations)} must match {sorted(step.target_properties)}."
        )

    total_spent = 0
    for prop_key, score in sorted(allocations.items()):
        if score < step.min_score or score > step.max_score:
            raise ValueError(
                f"Score {score} for '{prop_key}' outside [{step.min_score}, {step.max_score}]."
            )
        if step.cost_table:
            if score not in step.cost_table:
                raise ValueError(f"Missing point-buy cost_table entry for score {score}.")
            total_spent += step.cost_table[score]
        else:
            total_spent += score - step.base_value

    if total_spent > step.budget_points:
        raise ValueError(
            f"Point-buy cost {total_spent} exceeds budget of {step.budget_points} points."
        )

    props = dict(session.base_properties)
    for k, v in allocations.items():
        props[k] = v
    return session.model_copy(
        update={
            "base_properties": props,
            "completed_steps": _mark_completed(session.completed_steps, step.step_id),
        }
    )


def apply_standard_array(
    session: CreationSessionState,
    step: StandardArrayStepSpec,
    assignments: Mapping[str, int],
) -> CreationSessionState:
    """Validate exact multiset assignment of array_values onto target_properties."""
    if len(step.target_properties) != len(step.array_values):
        raise ValueError("Standard array length must match target_properties length.")
    if set(assignments.keys()) != set(step.target_properties):
        raise ValueError("Assignments must include every target property exactly once.")
    if sorted(assignments.values()) != sorted(step.array_values):
        raise ValueError(
            f"Assigned values {sorted(assignments.values())} do not match "
            f"{sorted(step.array_values)}."
        )

    props = dict(session.base_properties)
    for k, v in assignments.items():
        props[k] = v
    return session.model_copy(
        update={
            "base_properties": props,
            "completed_steps": _mark_completed(session.completed_steps, step.step_id),
        }
    )


def roll_random_attributes(
    session: CreationSessionState,
    step: RandomRollStepSpec,
    rng_registry: SceneRngRegistry,
) -> tuple[CreationSessionState, tuple[int | float, ...]]:
    """Roll deterministic attribute pool using the creation RNG stream."""
    stream = rng_registry.stream("creation")
    attempts = 0
    rolled: tuple[int | float, ...] = ()
    while True:
        values = [
            resolve_randomizer(step.roll_spec, stream, {})[0].total for _ in step.target_properties
        ]
        rolled = tuple(values)
        attempts += 1
        if (
            step.min_total_mercy is None
            or sum(values) >= step.min_total_mercy
            or attempts > step.max_rerolls
        ):
            break

    if step.assign_mode == "in_order":
        props = dict(session.base_properties)
        for prop_id, val in zip(step.target_properties, rolled, strict=True):
            props[prop_id] = val
        next_session = session.model_copy(
            update={
                "base_properties": props,
                "completed_steps": _mark_completed(session.completed_steps, step.step_id),
            }
        )
        return next_session, rolled

    pools_map = dict(session.pending_roll_pool)
    pools_map[step.step_id] = rolled
    return session.model_copy(update={"pending_roll_pool": pools_map}), rolled


def assign_rolled_attributes(
    session: CreationSessionState,
    step: RandomRollStepSpec,
    assignments: Mapping[str, int | float],
) -> CreationSessionState:
    """Assign values rolled in pool_assign mode onto target_properties."""
    pool = session.pending_roll_pool.get(step.step_id)
    if pool is None:
        raise ValueError(f"No rolled pool found for step '{step.step_id}'.")
    if set(assignments.keys()) != set(step.target_properties):
        raise ValueError("Assignments must cover every target property.")
    if sorted(assignments.values()) != sorted(pool):
        raise ValueError("Assigned values must exactly match rolled pool values.")

    props = dict(session.base_properties)
    for k, v in assignments.items():
        props[k] = v
    next_pools_map = dict(session.pending_roll_pool)
    next_pools_map.pop(step.step_id, None)
    return session.model_copy(
        update={
            "base_properties": props,
            "pending_roll_pool": next_pools_map,
            "completed_steps": _mark_completed(session.completed_steps, step.step_id),
        }
    )


def apply_package_pick(
    ruleset: RulesetSchema,
    session: CreationSessionState,
    step: PackagePickStepSpec,
    option_id: str,
    sub_selections: Mapping[str, Sequence[str]] | None = None,
) -> CreationSessionState:
    """Validate prerequisites & sub-choices and apply a package bundle."""
    option = next((opt for opt in step.options if opt.option_id == option_id), None)
    if option is None:
        raise KeyError(f"Unknown package option '{option_id}' in step '{step.step_id}'.")

    cur_view = compute_entity_view(ruleset, _session_to_entity(session))
    eval_ctx = {"@self": cur_view.to_eval_context()}
    if not bool(evaluate_formula(option.requires, eval_ctx)):
        raise PermissionError(f"Prerequisites not met for package option '{option_id}'.")

    props = dict(session.base_properties)
    tags = set(session.tags)
    actions = set(session.granted_actions)

    for k, val in option.property_sets.items():
        props[k] = val
    _apply_bonuses(props, option.property_bonuses)
    tags.update(option.granted_tags)
    actions.update(option.granted_actions)

    sel_map = sub_selections or {}
    for sub in option.sub_choices:
        chosen_ids = list(sel_map.get(sub.choice_id, ()))
        if len(chosen_ids) != sub.pick_count or len(set(chosen_ids)) != sub.pick_count:
            raise ValueError(
                f"Sub-choice '{sub.choice_id}' requires exactly {sub.pick_count} distinct picks."
            )
        opt_by_id = {o.option_id: o for o in sub.options}
        for cid in chosen_ids:
            picked = opt_by_id.get(cid)
            if picked is None:
                raise KeyError(f"Unknown sub-choice option '{cid}' in '{sub.choice_id}'.")
            _apply_bonuses(props, picked.property_bonuses)
            tags.update(picked.granted_tags)
            actions.update(picked.granted_actions)

    return session.model_copy(
        update={
            "base_properties": props,
            "tags": tuple(sorted(tags)),
            "granted_actions": tuple(sorted(actions)),
            "completed_steps": _mark_completed(session.completed_steps, step.step_id),
        }
    )


def step_lifepath_term(
    ruleset: RulesetSchema,
    session: CreationSessionState,
    step: LifepathChainStepSpec,
    career_id: str,
    rng_registry: SceneRngRegistry,
) -> tuple[CreationSessionState, LifepathTermOutcome]:
    """Execute a single term in a procedural lifepath career chain."""
    if session.lifepath_terms >= step.max_terms:
        raise ValueError(f"Maximum lifepath terms ({step.max_terms}) reached.")
    career = next((c for c in step.careers if c.career_id == career_id), None)
    if career is None:
        raise KeyError(f"Unknown lifepath career '{career_id}'.")

    cur_view = compute_entity_view(ruleset, _session_to_entity(session))
    eval_ctx = {"@self": cur_view.to_eval_context()}
    if not bool(evaluate_formula(career.requires, eval_ctx)):
        raise PermissionError(f"Prerequisites not met for career '{career_id}'.")

    stream = rng_registry.stream("creation")
    surv_roll, _ = resolve_randomizer(career.survival_roll, stream, eval_ctx)
    survived = surv_roll.total >= career.survival_target

    props = dict(session.base_properties)
    tags = set(session.tags)
    actions = set(session.granted_actions)

    _apply_bonuses(props, career.term_property_bonuses)

    event_id: str | None = None
    if career.events:
        chosen_evt = stream.choice(career.events)
        event_id = chosen_evt.event_id
        _apply_bonuses(props, chosen_evt.property_bonuses)
        tags.update(chosen_evt.granted_tags)
        actions.update(chosen_evt.granted_actions)

    promoted = False
    new_rank = session.lifepath_rank
    if survived:
        promo_roll, _ = resolve_randomizer(career.promotion_roll, stream, eval_ctx)
        if promo_roll.total >= career.promotion_target:
            promoted = True
            new_rank += 1

    term_num = session.lifepath_terms + 1
    outcome = LifepathTermOutcome(
        career_id=career_id,
        term_number=term_num,
        survived=survived,
        promoted=promoted,
        event_id=event_id,
    )
    updated = session.model_copy(
        update={
            "base_properties": props,
            "tags": tuple(sorted(tags)),
            "granted_actions": tuple(sorted(actions)),
            "lifepath_terms": term_num,
            "lifepath_rank": new_rank,
            "lifepath_history": (*session.lifepath_history, outcome),
        }
    )
    return updated, outcome


def muster_out_lifepath(
    session: CreationSessionState,
    step: LifepathChainStepSpec,
    career_id: str,
    *,
    currency_pool_id: str = "currency",
) -> CreationSessionState:
    """Finalize a lifepath career, banking mustering-out wealth and completing the step."""
    career = next((c for c in step.careers if c.career_id == career_id), None)
    if career is None:
        raise KeyError(f"Unknown lifepath career '{career_id}'.")
    if session.lifepath_terms < 1:
        raise ValueError("Must serve at least one lifepath term before mustering out.")

    pools = dict(session.pools)
    pools[currency_pool_id] = pools.get(currency_pool_id, 0) + (
        career.mustering_currency_per_term * session.lifepath_terms
    )
    tags = tuple(sorted(set(session.tags) | set(career.mustering_tags)))
    return session.model_copy(
        update={
            "pools": pools,
            "tags": tags,
            "completed_steps": _mark_completed(session.completed_steps, step.step_id),
        }
    )


def finalize_character(
    graph: CreationGraphSpec,
    ruleset: RulesetSchema,
    session: CreationSessionState,
) -> tuple[EntityState, ComputedEntityView]:
    """Validate all CreationGraphSpec steps are done and return initial EntityState + view."""
    missing = [s.step_id for s in graph.steps if s.step_id not in session.completed_steps]
    if missing:
        raise ValueError(f"Incomplete character creation steps: {missing}")
    entity = _session_to_entity(session)
    return entity, compute_entity_view(ruleset, entity)


# --- Part B: Five Progression / Advancement Paradigms ---


class LevelTierGrant(BaseModel):
    """Mechanical grants unlocked upon reaching a specific tier/milestone."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tier: int = Field(ge=1)
    xp_required: int = Field(ge=0)
    property_bonuses: dict[str, int | float] = Field(default_factory=_empty_str_float_dict)
    pool_max_bonuses: dict[str, int] = Field(default_factory=_empty_str_int_dict)
    granted_actions: tuple[str, ...] = ()
    granted_tags: tuple[str, ...] = ()


class ArchetypeOption(BaseModel):
    """Tier-up archetype or multiclass option gated by AST prerequisites."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    option_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    requires: str = "true"
    property_bonuses: dict[str, int | float] = Field(default_factory=_empty_str_float_dict)
    granted_actions: tuple[str, ...] = ()
    granted_tags: tuple[str, ...] = ()


class LevelUpParadigmSpec(BaseModel):
    """Paradigm 1: Tiered Level & Milestone Progression."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    paradigm: Literal["level_up_graph"] = "level_up_graph"
    tiers: tuple[LevelTierGrant, ...] = Field(min_length=1)
    archetype_options: tuple[ArchetypeOption, ...] = ()


class XpStoreEntry(BaseModel):
    """Purchasable advance in a Classless XP / Karma Store or Playbook."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    entry_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    cost_formula: str = "0"
    requires: str = "true"
    max_rank: int | None = None
    target_property: str | None = None
    property_step: int | float = 1
    granted_actions: tuple[str, ...] = ()
    granted_tags: tuple[str, ...] = ()


class XpStoreParadigmSpec(BaseModel):
    """Paradigm 2: Classless XP / Karma Point-Buy Store."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    paradigm: Literal["xp_store"] = "xp_store"
    entries: dict[str, XpStoreEntry] = Field(default_factory=dict)


class SkillTicksParadigmSpec(BaseModel):
    """Paradigm 3: Usage-Driven Skill Ticks & Roll-to-Improve (BRP / d100 style)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    paradigm: Literal["skill_usage_ticks"] = "skill_usage_ticks"
    tick_tag_prefix: str = "skill_tick:"
    check_roll: RandomizerSpec = Field(
        default_factory=lambda: RandomizerSpec(kind="dice_formula", formula="1d100")
    )
    gain_roll: RandomizerSpec = Field(
        default_factory=lambda: RandomizerSpec(kind="dice_formula", formula="1d10")
    )
    max_skill_value: int = Field(default=100, ge=1)


class PlaybookTriggersParadigmSpec(BaseModel):
    """Paradigm 4: Narrative Playbook XP Triggers & Clock Wrapping (PbtA / FitD style)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    paradigm: Literal["playbook_triggers"] = "playbook_triggers"
    triggers: tuple[str, ...] = Field(min_length=1)
    xp_clock_pool_id: str = "playbook_xp"
    advancement_threshold: int = Field(default=8, ge=1)


class TrainingTechniqueSpec(BaseModel):
    """Technique or upgrade unlocked via in-world trainer, facility, ticks, and fee."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    technique_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    required_trainer_tag: str = ""
    required_facility_tag: str = ""
    required_downtime_ticks: int = Field(default=0, ge=0)
    currency_cost: int = Field(default=0, ge=0)
    requires: str = "true"
    property_bonuses: dict[str, int | float] = Field(default_factory=_empty_str_float_dict)
    granted_actions: tuple[str, ...] = ()
    granted_tags: tuple[str, ...] = ()


class DiegeticTrainingParadigmSpec(BaseModel):
    """Paradigm 5: Diegetic In-World Training, Manuals & Augmentations."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    paradigm: Literal["diegetic_training"] = "diegetic_training"
    techniques: dict[str, TrainingTechniqueSpec] = Field(default_factory=dict)


class AdvancementGraphSpec(BaseModel):
    """Declarative bundle of supported progression paradigms in a ruleset."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    level_up: LevelUpParadigmSpec | None = None
    xp_store: XpStoreParadigmSpec | None = None
    skill_ticks: SkillTicksParadigmSpec | None = None
    playbook_triggers: PlaybookTriggersParadigmSpec | None = None
    diegetic_training: DiegeticTrainingParadigmSpec | None = None


class PropertyDiff(BaseModel):
    """Before -> After value delta for a single property during advancement."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    before: ScalarValue
    after: ScalarValue


class PoolDiff(BaseModel):
    """Before -> After delta for a resource pool during advancement."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    before: int
    after: int


class AdvancementDiff(BaseModel):
    """Structured Before -> After diff rendered inside the UI Advancement Drawer."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    property_changes: dict[str, PropertyDiff] = Field(default_factory=dict)
    pool_changes: dict[str, PoolDiff] = Field(default_factory=dict)
    added_actions: tuple[str, ...] = ()
    added_tags: tuple[str, ...] = ()
    cost_spent: dict[str, int] = Field(default_factory=_empty_str_int_dict)


class AdvancementResult(BaseModel):
    """Completed advancement output pairing updated EntityState, Before/After diff & event."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    entity: EntityState
    before_view: ComputedEntityView
    after_view: ComputedEntityView
    diff: AdvancementDiff
    event: VmEvent


def _build_advancement_result(
    ruleset: RulesetSchema,
    before_entity: EntityState,
    after_entity: EntityState,
    *,
    added_tags: Sequence[str],
    removed_tags: Sequence[str],
    added_actions: Sequence[str],
    cost_spent: dict[str, int],
    actor_seat_id: str,
    scene_id: str,
    event_seq: int,
    reason: str,
) -> AdvancementResult:
    before_view = compute_entity_view(ruleset, before_entity)
    after_view = compute_entity_view(ruleset, after_entity)

    prop_changes: dict[str, PropertyDiff] = {}
    for pid in sorted(set(before_view.properties) | set(after_view.properties)):
        b_val = before_view.properties.get(pid)
        a_val = after_view.properties.get(pid)
        if b_val != a_val:
            prop_changes[pid] = PropertyDiff(before=b_val, after=a_val)

    pool_changes: dict[str, PoolDiff] = {}
    for pool_id in sorted(set(before_entity.pools) | set(after_entity.pools)):
        b_p = before_entity.pools.get(pool_id, 0)
        a_p = after_entity.pools.get(pool_id, 0)
        if b_p != a_p:
            pool_changes[pool_id] = PoolDiff(before=b_p, after=a_p)

    prop_updates = {
        k: v
        for k, v in after_entity.base_properties.items()
        if before_entity.base_properties.get(k) != v
    }
    pool_updates = {k: v for k, v in after_entity.pools.items() if before_entity.pools.get(k) != v}

    diff = AdvancementDiff(
        property_changes=prop_changes,
        pool_changes=pool_changes,
        added_actions=tuple(sorted(set(added_actions) - set(before_entity.granted_actions))),
        added_tags=tuple(sorted(set(added_tags) - set(before_entity.tags))),
        cost_spent=cost_spent,
    )
    event = VmEvent(
        event_id=f"evt_{scene_id}_{event_seq + 1:06d}",
        event_type="CHARACTER_ADVANCED",
        actor_id=actor_seat_id,
        payload={
            "entity_id": before_entity.entity_id,
            "reason": reason,
            "property_updates": prop_updates,
            "pool_updates": pool_updates,
            "added_tags": list(added_tags),
            "removed_tags": list(removed_tags),
            "added_actions": list(added_actions),
        },
    )
    return AdvancementResult(
        entity=after_entity,
        before_view=before_view,
        after_view=after_view,
        diff=diff,
        event=event,
    )


def check_tier_up_eligible(
    entity: EntityState,
    spec: LevelUpParadigmSpec,
    *,
    tier_prop_id: str = "tier",
    xp_pool_id: str = "xp",
) -> int | None:
    """Return next eligible tier number if XP meets requirement, else None."""
    cur_tier_raw = entity.base_properties.get(tier_prop_id, 1)
    cur_tier = int(cur_tier_raw) if isinstance(cur_tier_raw, (int, float)) else 1
    next_grant = next((t for t in spec.tiers if t.tier == cur_tier + 1), None)
    if next_grant is None:
        return None
    if entity.pools.get(xp_pool_id, 0) >= next_grant.xp_required:
        return next_grant.tier
    return None


def apply_tier_up(
    ruleset: RulesetSchema,
    entity: EntityState,
    spec: LevelUpParadigmSpec,
    target_tier: int,
    *,
    archetype_choice_id: str | None = None,
    tier_prop_id: str = "tier",
    xp_pool_id: str = "xp",
    milestone: bool = False,
    actor_seat_id: str = "player",
    scene_id: str = "scene",
    event_seq: int = 0,
) -> AdvancementResult:
    """Advance entity to target_tier, enforcing XP/milestone & multiclass prerequisites."""
    grant = next((t for t in spec.tiers if t.tier == target_tier), None)
    if grant is None:
        raise KeyError(f"Unknown advancement tier {target_tier}.")
    if not milestone and entity.pools.get(xp_pool_id, 0) < grant.xp_required:
        raise ValueError(
            f"Insufficient XP ({entity.pools.get(xp_pool_id, 0)} < {grant.xp_required})."
        )

    props = dict(entity.base_properties)
    pools = dict(entity.pools)
    tags = set(entity.tags)
    actions = set(entity.granted_actions)

    new_tags: list[str] = []
    new_actions: list[str] = []

    if archetype_choice_id is not None:
        arch = next(
            (a for a in spec.archetype_options if a.option_id == archetype_choice_id),
            None,
        )
        if arch is None:
            raise KeyError(f"Unknown archetype option '{archetype_choice_id}'.")
        cur_view = compute_entity_view(ruleset, entity)
        if not bool(evaluate_formula(arch.requires, {"@self": cur_view.to_eval_context()})):
            raise PermissionError(
                f"Multiclass/archetype prerequisites failed for '{arch.option_id}'."
            )
        _apply_bonuses(props, arch.property_bonuses)
        new_tags.extend(arch.granted_tags)
        new_actions.extend(arch.granted_actions)

    props[tier_prop_id] = target_tier
    _apply_bonuses(props, grant.property_bonuses)
    for pool_id, delta in sorted(grant.pool_max_bonuses.items()):
        pools[pool_id] = pools.get(pool_id, 0) + delta
    new_tags.extend(grant.granted_tags)
    new_actions.extend(grant.granted_actions)

    tags.update(new_tags)
    actions.update(new_actions)

    after_entity = entity.model_copy(
        update={
            "base_properties": props,
            "pools": pools,
            "tags": tuple(sorted(tags)),
            "granted_actions": tuple(sorted(actions)),
        }
    )
    return _build_advancement_result(
        ruleset,
        entity,
        after_entity,
        added_tags=new_tags,
        removed_tags=(),
        added_actions=new_actions,
        cost_spent={},
        actor_seat_id=actor_seat_id,
        scene_id=scene_id,
        event_seq=event_seq,
        reason=f"tier_up:{target_tier}",
    )


def purchase_xp_store_item(
    ruleset: RulesetSchema,
    entity: EntityState,
    spec: XpStoreParadigmSpec,
    entry_id: str,
    *,
    currency_pool_id: str = "xp",
    actor_seat_id: str = "player",
    scene_id: str = "scene",
    event_seq: int = 0,
) -> AdvancementResult:
    """Purchase a single entry in a classless XP / Karma store."""
    entry = spec.entries.get(entry_id)
    if entry is None:
        raise KeyError(f"Unknown XP store entry '{entry_id}'.")

    cur_view = compute_entity_view(ruleset, entity)
    eval_ctx = {"@self": cur_view.to_eval_context()}
    if not bool(evaluate_formula(entry.requires, eval_ctx)):
        raise PermissionError(f"Prerequisites failed for XP store entry '{entry_id}'.")

    cost_raw = evaluate_formula(entry.cost_formula, eval_ctx)
    if isinstance(cost_raw, bool) or not isinstance(cost_raw, (int, float)):
        raise ValueError(f"Invalid cost formula output {cost_raw!r} for '{entry_id}'.")
    cost = int(cost_raw)
    cur_xp = entity.pools.get(currency_pool_id, 0)
    if cur_xp < cost:
        raise ValueError(f"Insufficient {currency_pool_id} ({cur_xp} < {cost}).")

    props = dict(entity.base_properties)
    if entry.target_property is not None:
        cur_rank = props.get(entry.target_property, 0)
        cur_num = (
            cur_rank if isinstance(cur_rank, (int, float)) and not isinstance(cur_rank, bool) else 0
        )
        next_rank = cur_num + entry.property_step
        if entry.max_rank is not None and next_rank > entry.max_rank:
            raise ValueError(
                f"Property '{entry.target_property}' already at max_rank ({entry.max_rank})."
            )
        props[entry.target_property] = next_rank

    pools = dict(entity.pools)
    pools[currency_pool_id] = cur_xp - cost
    tags = set(entity.tags)
    tags.update(entry.granted_tags)
    actions = set(entity.granted_actions)
    actions.update(entry.granted_actions)

    after_entity = entity.model_copy(
        update={
            "base_properties": props,
            "pools": pools,
            "tags": tuple(sorted(tags)),
            "granted_actions": tuple(sorted(actions)),
        }
    )
    return _build_advancement_result(
        ruleset,
        entity,
        after_entity,
        added_tags=entry.granted_tags,
        removed_tags=(),
        added_actions=entry.granted_actions,
        cost_spent={currency_pool_id: cost},
        actor_seat_id=actor_seat_id,
        scene_id=scene_id,
        event_seq=event_seq,
        reason=f"xp_store:{entry_id}",
    )


def mark_skill_tick(
    entity: EntityState,
    skill_prop_id: str,
    *,
    tick_tag_prefix: str = "skill_tick:",
) -> EntityState:
    """Attach an improvement_tick tag for usage-driven progression."""
    tick_tag = f"{tick_tag_prefix}{skill_prop_id}"
    if tick_tag in entity.tags:
        return entity
    return entity.model_copy(update={"tags": tuple(sorted([*entity.tags, tick_tag]))})


def resolve_skill_improvement_pass(
    ruleset: RulesetSchema,
    entity: EntityState,
    spec: SkillTicksParadigmSpec,
    skill_prop_ids: Sequence[str],
    rng_registry: SceneRngRegistry,
    *,
    actor_seat_id: str = "player",
    scene_id: str = "scene",
    event_seq: int = 0,
) -> AdvancementResult:
    """Roll improvement checks for every ticked skill in skill_prop_ids."""
    stream = rng_registry.stream("advancement")
    props = dict(entity.base_properties)
    tags = set(entity.tags)
    removed_ticks: list[str] = []

    for skill_id in sorted(set(skill_prop_ids)):
        tick_tag = f"{spec.tick_tag_prefix}{skill_id}"
        if tick_tag not in tags:
            continue
        tags.discard(tick_tag)
        removed_ticks.append(tick_tag)

        cur_val_raw = props.get(skill_id, 0)
        cur_val = int(cur_val_raw) if isinstance(cur_val_raw, (int, float)) else 0
        check_res, _ = resolve_randomizer(spec.check_roll, stream, {})
        if check_res.total > cur_val:
            gain_res, _ = resolve_randomizer(spec.gain_roll, stream, {})
            improved = min(spec.max_skill_value, cur_val + int(gain_res.total))
            props[skill_id] = improved

    after_entity = entity.model_copy(
        update={
            "base_properties": props,
            "tags": tuple(sorted(tags)),
        }
    )
    return _build_advancement_result(
        ruleset,
        entity,
        after_entity,
        added_tags=(),
        removed_tags=removed_ticks,
        added_actions=(),
        cost_spent={},
        actor_seat_id=actor_seat_id,
        scene_id=scene_id,
        event_seq=event_seq,
        reason="skill_improvement_pass",
    )


def apply_playbook_triggers(
    ruleset: RulesetSchema,
    entity: EntityState,
    spec: PlaybookTriggersParadigmSpec,
    answered_triggers: Sequence[str],
    *,
    chosen_upgrade: XpStoreEntry | None = None,
    actor_seat_id: str = "player",
    scene_id: str = "scene",
    event_seq: int = 0,
) -> AdvancementResult:
    """Mark end-of-session playbook triggers, advance XP clock, and optionally claim an advance."""
    valid_set = set(spec.triggers)
    earned_set = {t for t in answered_triggers if t in valid_set}
    if len(earned_set) != len(set(answered_triggers)):
        unknown = sorted(set(answered_triggers) - valid_set)
        raise KeyError(f"Unknown playbook trigger(s): {unknown}")

    pools = dict(entity.pools)
    cur_clock = pools.get(spec.xp_clock_pool_id, 0) + len(earned_set)
    props = dict(entity.base_properties)
    tags = set(entity.tags)
    actions = set(entity.granted_actions)
    added_tags: tuple[str, ...] = ()
    added_actions: tuple[str, ...] = ()

    if chosen_upgrade is not None:
        if cur_clock < spec.advancement_threshold:
            raise ValueError(
                f"Playbook clock {cur_clock} below threshold {spec.advancement_threshold}."
            )
        cur_clock -= spec.advancement_threshold
        if chosen_upgrade.target_property is not None:
            cur_val = props.get(chosen_upgrade.target_property, 0)
            num_val = (
                cur_val
                if isinstance(cur_val, (int, float)) and not isinstance(cur_val, bool)
                else 0
            )
            props[chosen_upgrade.target_property] = num_val + chosen_upgrade.property_step
        tags.update(chosen_upgrade.granted_tags)
        actions.update(chosen_upgrade.granted_actions)
        added_tags = chosen_upgrade.granted_tags
        added_actions = chosen_upgrade.granted_actions

    pools[spec.xp_clock_pool_id] = cur_clock
    after_entity = entity.model_copy(
        update={
            "base_properties": props,
            "pools": pools,
            "tags": tuple(sorted(tags)),
            "granted_actions": tuple(sorted(actions)),
        }
    )
    return _build_advancement_result(
        ruleset,
        entity,
        after_entity,
        added_tags=added_tags,
        removed_tags=(),
        added_actions=added_actions,
        cost_spent={},
        actor_seat_id=actor_seat_id,
        scene_id=scene_id,
        event_seq=event_seq,
        reason="playbook_triggers",
    )


def complete_diegetic_training(
    ruleset: RulesetSchema,
    entity: EntityState,
    spec: DiegeticTrainingParadigmSpec,
    technique_id: str,
    *,
    available_context_tags: Sequence[str],
    downtime_ticks_logged: int,
    currency_pool_id: str = "currency",
    actor_seat_id: str = "player",
    scene_id: str = "scene",
    event_seq: int = 0,
) -> AdvancementResult:
    """Verify trainer/facility/downtime/fee gates and grant diegetic training rewards."""
    tech = spec.techniques.get(technique_id)
    if tech is None:
        raise KeyError(f"Unknown diegetic training technique '{technique_id}'.")

    ctx_tag_set = set(available_context_tags)
    if tech.required_trainer_tag and tech.required_trainer_tag not in ctx_tag_set:
        raise PermissionError(f"Missing required trainer tag '{tech.required_trainer_tag}'.")
    if tech.required_facility_tag and tech.required_facility_tag not in ctx_tag_set:
        raise PermissionError(f"Missing required facility tag '{tech.required_facility_tag}'.")
    if downtime_ticks_logged < tech.required_downtime_ticks:
        raise ValueError(
            f"Insufficient training ticks ({downtime_ticks_logged} < "
            f"{tech.required_downtime_ticks})."
        )

    cur_view = compute_entity_view(ruleset, entity)
    if not bool(evaluate_formula(tech.requires, {"@self": cur_view.to_eval_context()})):
        raise PermissionError(f"Prerequisites failed for training '{technique_id}'.")

    cur_currency = entity.pools.get(currency_pool_id, 0)
    if cur_currency < tech.currency_cost:
        raise ValueError(f"Insufficient currency ({cur_currency} < {tech.currency_cost}).")

    props = dict(entity.base_properties)
    _apply_bonuses(props, tech.property_bonuses)
    pools = dict(entity.pools)
    pools[currency_pool_id] = cur_currency - tech.currency_cost
    tags = set(entity.tags)
    tags.update(tech.granted_tags)
    actions = set(entity.granted_actions)
    actions.update(tech.granted_actions)

    after_entity = entity.model_copy(
        update={
            "base_properties": props,
            "pools": pools,
            "tags": tuple(sorted(tags)),
            "granted_actions": tuple(sorted(actions)),
        }
    )
    return _build_advancement_result(
        ruleset,
        entity,
        after_entity,
        added_tags=tech.granted_tags,
        removed_tags=(),
        added_actions=tech.granted_actions,
        cost_spent={currency_pool_id: tech.currency_cost} if tech.currency_cost else {},
        actor_seat_id=actor_seat_id,
        scene_id=scene_id,
        event_seq=event_seq,
        reason=f"diegetic_training:{technique_id}",
    )
