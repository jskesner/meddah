"""Universal agnostic Ruleset Building Block schemas (Golden Rule #1)."""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.ruleset_vm.ast_evaluator import (
    FormulaError,
    ScalarValue,
    extract_references,
    parse_formula,
)
from app.ruleset_vm.manifest import PackageManifest

RandomizerKind = Literal[
    "dice_formula",
    "dice_pool",
    "step_dice",
    "coin_flip",
    "card_deck",
    "resource_wager",
    "none",
]


class PropertyBlock(BaseModel):
    """Named attribute, derived statistic, or descriptive trait on an entity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    prop_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    value_kind: Literal["int", "float", "bool", "str", "step_die"] = "int"
    default_value: ScalarValue = 0
    min_value: int | float | None = None
    max_value: int | float | None = None
    formula: str | None = Field(
        default=None,
        description="Optional AST formula deriving this property from other entity properties.",
    )
    category: str = "core"
    tags: tuple[str, ...] = ()


class ResourcePoolBlock(BaseModel):
    """Depletable/recoverable track or pool (vitality, stamina, stress, doom clock, etc.)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    pool_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    default_current: str | int = 0
    max_formula: str | None = None
    min_value: int = 0
    reset_on: str = "manual"
    track_segments: int | None = Field(default=None, ge=1)


class EffectSpec(BaseModel):
    """Deterministic state mutation emitted by actions, tiers, or ECA event hooks."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal[
        "modify_pool",
        "set_property",
        "add_condition",
        "remove_condition",
        "advance_clock",
        "emit_message",
        "shift_form",
        "revert_form",
        "set_awareness",
        "apply_disguise",
        "reveal_disguise",
        "transfer_item",
        "mark_provenance",
    ]
    target_scope: Literal["self", "target", "scene"] = "target"
    target_key: str = ""
    formula: str = "0"
    duration_turns: int | None = Field(default=None, ge=1)
    forced: bool = False


class OutcomeTier(BaseModel):
    """Ordered outcome predicate and resulting effects for a resolution mechanic."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tier_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    condition: str = Field(min_length=1)
    effects: tuple[EffectSpec, ...] = ()


def _empty_face_symbols() -> dict[int, tuple[str, ...]]:
    return {}


class RandomizerSpec(BaseModel):
    """Declarative specification of dice, pool, step-die, deck, wager, or diceless rolls."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: RandomizerKind = "dice_formula"
    formula: str = ""
    pool_size_formula: str = "1"
    die_sides: int = Field(default=6, ge=2, le=1000)
    success_threshold: int = 5
    glitch_face: int = 1
    glitch_ratio: float = Field(default=0.5, ge=0.0, le=1.0)
    step_die_formula: str = ""
    wild_die_sides: int | None = Field(default=None, ge=2, le=100)
    explode: bool = False
    face_symbols: dict[int, tuple[str, ...]] = Field(default_factory=_empty_face_symbols)
    coin_heads_label: str = Field(default="heads", min_length=1)
    coin_tails_label: str = Field(default="tails", min_length=1)
    deck_id: str | None = None
    draw_count: int = Field(default=1, ge=1, le=52)
    reshuffle_on_empty: bool = True
    base_value: int | float = 0


class ResolutionMechanicBlock(BaseModel):
    """Combines a randomizer, modifiers, target difficulty, and outcome tiers."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mech_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    randomizer: RandomizerSpec
    modifier_formula: str = "0"
    target_formula: str | None = None
    resolution_mode: Literal["standard", "contested"] = "standard"
    opposed_mech_id: str | None = None
    tiers: tuple[OutcomeTier, ...] = ()


class ConditionBlock(BaseModel):
    """Status condition with declarative property deltas and capability gating tags."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    condition_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    description: str = ""
    property_modifiers: dict[str, str] = Field(default_factory=dict)
    blocks_tags: tuple[str, ...] = ()
    persistent_flag: bool = False
    default_duration_turns: int | None = Field(default=None, ge=1)
    visual_priority: int = 0


class ActionBlock(BaseModel):
    """Player or NPC capability/action/stance/reaction executed through the VM."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    action_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    category: Literal["action", "power", "reaction", "stance"] = "action"
    resolution_id: str | None = None
    requires: str = "true"
    pool_costs: dict[str, str] = Field(default_factory=dict)
    allow_reactions: bool = False
    trigger: str | None = None
    requires_target: bool = False
    target_override_formula: str | None = None
    modifier_override_formula: str | None = None
    default_effects: tuple[EffectSpec, ...] = ()
    tags: tuple[str, ...] = ()


class EventHookBlock(BaseModel):
    """Declarative Event-Condition-Action (ECA) hook bound to VM lifecycle events."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    hook_id: str = Field(min_length=1)
    event_name: str = Field(min_length=1)
    condition: str = "true"
    effects: tuple[EffectSpec, ...] = ()


class DeckSpec(BaseModel):
    """Named card deck specification supporting multiple gameplay scopes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    deck_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    scope: Literal["table_shared", "per_entity", "encounter_local"] = "table_shared"
    cards: tuple[str, ...] = Field(min_length=1)
    card_values: dict[str, int] = Field(default_factory=dict)


class FlowConfig(BaseModel):
    """Pluggable turn/time flow configuration for a ruleset."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    default_mode: Literal["freeform", "round_initiative", "popcorn_spotlight"] = "freeform"
    initiative_formula: str = "0"
    turn_pool_resets: tuple[str, ...] = ()


FormPropertyMode = Literal["replace_all", "replace_subset", "delta_overlay"]
FormPoolMode = Literal["separate_form_pool", "shared_base_pool", "temp_bonus_pool"]
GearHandlingMode = Literal["merge_into_form", "keep_worn", "drop_to_room"]


def _empty_form_pool_dict() -> dict[str, FormPoolSpec]:
    return {}


class FormPoolSpec(BaseModel):
    """Per-pool policy governing how a ResourcePool behaves while transformed into a form."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: FormPoolMode = "separate_form_pool"
    initial_formula: str = "0"
    max_formula: str | None = None
    overflow_to_base: bool = True
    auto_revert_on_zero: bool = True


class FormBlock(BaseModel):
    """Declarative alternate form, transformation, chassis, or shape-shift stat block."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    form_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    description: str = ""
    requires: str = "true"
    pool_costs: dict[str, str] = Field(default_factory=dict)
    property_mode: FormPropertyMode = "replace_subset"
    property_values: dict[str, ScalarValue] = Field(default_factory=dict)
    property_deltas: dict[str, str] = Field(default_factory=dict)
    pool_policies: dict[str, FormPoolSpec] = Field(default_factory=_empty_form_pool_dict)
    action_mode: Literal["merge", "replace"] = "merge"
    granted_actions: tuple[str, ...] = ()
    blocked_tags: tuple[str, ...] = ()
    granted_tags: tuple[str, ...] = ()
    gear_handling: GearHandlingMode = "merge_into_form"
    suppress_gear_auras: bool = True
    default_duration_turns: int | None = Field(default=None, ge=1)
    size_category: str | None = None
    anatomy_topology_override: str | None = None
    portrait_override_ref: str | None = None
    token_override_ref: str | None = None


PvpCovertPolicy = Literal["npc_only", "gm_approved", "unrestricted"]
CovertPillar = Literal["stealth", "theft", "disguise"]


class StealthPillarConfig(BaseModel):
    """Ruleset bindings for per-observer stealth awareness without overriding conditions."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    hide_action_ids: tuple[str, ...] = ()
    hidden_condition_ids: tuple[str, ...] = ()
    detection_action_ids: tuple[str, ...] = ()
    awareness_levels: tuple[str, ...] = ("unaware", "suspected", "searching", "detected")
    detected_level: str = "detected"
    unaware_level: str = "unaware"
    sync_hidden_condition_on_detect: bool = False
    noisy_action_tags: tuple[str, ...] = ()


class TheftPillarConfig(BaseModel):
    """Ruleset bindings for item theft, evidence planting, lockpicking & delayed notice."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    steal_action_ids: tuple[str, ...] = ()
    plant_action_ids: tuple[str, ...] = ()
    lockpick_action_ids: tuple[str, ...] = ()
    stolen_tag: str = "stolen"
    planted_tag: str = "planted"
    contraband_tag: str = "contraband"
    default_notice_delay_turns: int | None = Field(default=None, ge=1)


class DisguisePillarConfig(BaseModel):
    """Ruleset bindings for masked personas, disguise quality & scrutiny checks."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    disguise_action_ids: tuple[str, ...] = ()
    scrutiny_action_ids: tuple[str, ...] = ()
    disguised_condition_ids: tuple[str, ...] = ()
    requires_voice_modulation_for_speech: bool = False


class CovertOpsConfigBlock(BaseModel):
    """Granular 3-pillar covert bindings interpreting ruleset mechanics (ADR-0134)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    stealth: StealthPillarConfig | None = None
    theft: TheftPillarConfig | None = None
    disguise: DisguisePillarConfig | None = None

    def active_pillars(self) -> tuple[CovertPillar, ...]:
        """Return tuple of ruleset-declared covert pillars (empty when dormant)."""
        pillars: list[CovertPillar] = []
        if self.stealth is not None:
            pillars.append("stealth")
        if self.theft is not None:
            pillars.append("theft")
        if self.disguise is not None:
            pillars.append("disguise")
        return tuple(pillars)


class RulesetSchema(BaseModel):
    """Top-level declarative schema compiled from .rpgrules or authoring studios."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    manifest: PackageManifest
    declared_primitives: tuple[str, ...] = ()
    properties: dict[str, PropertyBlock] = Field(default_factory=dict)
    resource_pools: dict[str, ResourcePoolBlock] = Field(default_factory=dict)
    resolutions: dict[str, ResolutionMechanicBlock] = Field(default_factory=dict)
    conditions: dict[str, ConditionBlock] = Field(default_factory=dict)
    actions: dict[str, ActionBlock] = Field(default_factory=dict)
    event_hooks: dict[str, EventHookBlock] = Field(default_factory=dict)
    decks: dict[str, DeckSpec] = Field(default_factory=dict)
    forms: dict[str, FormBlock] = Field(default_factory=dict)
    flow_config: FlowConfig = Field(default_factory=FlowConfig)
    covert_ops: CovertOpsConfigBlock | None = None

    def content_hash(self) -> str:
        """Compute canonical SHA-256 digest of this ruleset schema."""
        serialized = json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def topological_property_order(self) -> tuple[str, ...]:
        """Return derived property IDs sorted with dependencies before dependents."""
        derived = {pid: prop for pid, prop in self.properties.items() if prop.formula is not None}
        deps: dict[str, set[str]] = {}
        for pid, prop in derived.items():
            assert prop.formula is not None
            refs = extract_references(prop.formula)
            prop_deps: set[str] = set()
            for ref in refs:
                if ref.startswith("@self."):
                    dep_name = ref.removeprefix("@self.").split(".")[0]
                    if dep_name in derived:
                        prop_deps.add(dep_name)
            deps[pid] = prop_deps

        order: list[str] = []
        state: dict[str, int] = {}

        def _visit(pid: str) -> None:
            mark = state.get(pid, 0)
            if mark == 1:
                raise FormulaError(
                    "RPG-E2001", f"Circular derived-property dependency involving '{pid}'"
                )
            if mark == 2:
                return
            state[pid] = 1
            for dep in sorted(deps.get(pid, ())):
                _visit(dep)
            state[pid] = 2
            order.append(pid)

        for pid in sorted(derived):
            _visit(pid)
        return tuple(order)

    def validate_graph(self) -> list[str]:
        """Validate internal formulas, circular dependencies, and cross-block references."""
        errors: list[str] = []

        for pid, prop in sorted(self.properties.items()):
            if prop.formula is not None:
                try:
                    parse_formula(prop.formula)
                except FormulaError as exc:
                    errors.append(f"Property '{pid}' invalid formula: {exc.message}")

        try:
            self.topological_property_order()
        except FormulaError as exc:
            errors.append(exc.message)

        for pool_id, pool in sorted(self.resource_pools.items()):
            if isinstance(pool.default_current, str):
                try:
                    parse_formula(pool.default_current)
                except FormulaError as exc:
                    errors.append(f"ResourcePool '{pool_id}' default_current: {exc.message}")
            if pool.max_formula is not None:
                try:
                    parse_formula(pool.max_formula)
                except FormulaError as exc:
                    errors.append(f"ResourcePool '{pool_id}' max_formula: {exc.message}")

        for mech_id, mech in sorted(self.resolutions.items()):
            for field_label, expr in (
                ("modifier_formula", mech.modifier_formula),
                ("target_formula", mech.target_formula),
            ):
                if expr is not None:
                    try:
                        parse_formula(expr)
                    except FormulaError as exc:
                        errors.append(f"Resolution '{mech_id}' {field_label}: {exc.message}")
            if mech.randomizer.kind in {"dice_pool", "coin_flip"}:
                try:
                    parse_formula(mech.randomizer.pool_size_formula)
                except FormulaError as exc:
                    errors.append(f"Resolution '{mech_id}' pool_size_formula: {exc.message}")
            if mech.randomizer.kind == "card_deck" and (
                mech.randomizer.deck_id is None or mech.randomizer.deck_id not in self.decks
            ):
                errors.append(
                    f"Resolution '{mech_id}' references unknown deck '{mech.randomizer.deck_id}'"
                )
            for tier in mech.tiers:
                try:
                    parse_formula(tier.condition)
                except FormulaError as exc:
                    errors.append(f"Resolution '{mech_id}' tier '{tier.tier_id}': {exc.message}")
                for eff in tier.effects:
                    self._validate_effect(
                        eff, f"Resolution '{mech_id}' tier '{tier.tier_id}'", errors
                    )

        for action_id, action in sorted(self.actions.items()):
            if action.resolution_id is not None and action.resolution_id not in self.resolutions:
                errors.append(
                    f"Action '{action_id}' references unknown resolution '{action.resolution_id}'"
                )
            for pool_key, cost_expr in sorted(action.pool_costs.items()):
                if pool_key not in self.resource_pools:
                    errors.append(
                        f"Action '{action_id}' pool cost references unknown pool '{pool_key}'"
                    )
                try:
                    parse_formula(cost_expr)
                except FormulaError as exc:
                    errors.append(f"Action '{action_id}' cost '{pool_key}': {exc.message}")
            for field_label, expr in (
                ("requires", action.requires),
                ("target_override_formula", action.target_override_formula),
                ("modifier_override_formula", action.modifier_override_formula),
            ):
                if expr is not None:
                    try:
                        parse_formula(expr)
                    except FormulaError as exc:
                        errors.append(f"Action '{action_id}' {field_label}: {exc.message}")
            for eff in action.default_effects:
                self._validate_effect(eff, f"Action '{action_id}'", errors)

        for hook_id, hook in sorted(self.event_hooks.items()):
            try:
                parse_formula(hook.condition)
            except FormulaError as exc:
                errors.append(f"EventHook '{hook_id}' condition: {exc.message}")
            for eff in hook.effects:
                self._validate_effect(eff, f"EventHook '{hook_id}'", errors)

        for form_id, form in sorted(self.forms.items()):
            try:
                parse_formula(form.requires)
            except FormulaError as exc:
                errors.append(f"Form '{form_id}' requires: {exc.message}")
            for pool_key, cost_expr in sorted(form.pool_costs.items()):
                if pool_key not in self.resource_pools:
                    errors.append(
                        f"Form '{form_id}' pool cost references unknown pool '{pool_key}'"
                    )
                try:
                    parse_formula(cost_expr)
                except FormulaError as exc:
                    errors.append(f"Form '{form_id}' cost '{pool_key}': {exc.message}")
            for prop_key, delta_expr in sorted(form.property_deltas.items()):
                try:
                    parse_formula(delta_expr)
                except FormulaError as exc:
                    errors.append(f"Form '{form_id}' property delta '{prop_key}': {exc.message}")
            for pool_key, policy in sorted(form.pool_policies.items()):
                try:
                    parse_formula(policy.initial_formula)
                except FormulaError as exc:
                    errors.append(
                        f"Form '{form_id}' pool '{pool_key}' initial_formula: {exc.message}"
                    )
                if policy.max_formula is not None:
                    try:
                        parse_formula(policy.max_formula)
                    except FormulaError as exc:
                        errors.append(
                            f"Form '{form_id}' pool '{pool_key}' max_formula: {exc.message}"
                        )

        if self.covert_ops is not None:
            if self.covert_ops.stealth is not None:
                st_cfg = self.covert_ops.stealth
                for aid in (*st_cfg.hide_action_ids, *st_cfg.detection_action_ids):
                    if aid not in self.actions:
                        errors.append(f"CovertOps stealth references unknown action '{aid}'")
                for cid in st_cfg.hidden_condition_ids:
                    if cid not in self.conditions:
                        errors.append(f"CovertOps stealth references unknown condition '{cid}'")
                if st_cfg.detected_level not in st_cfg.awareness_levels:
                    errors.append(
                        f"CovertOps stealth detected_level '{st_cfg.detected_level}' "
                        "is missing from awareness_levels"
                    )
                if st_cfg.unaware_level not in st_cfg.awareness_levels:
                    errors.append(
                        f"CovertOps stealth unaware_level '{st_cfg.unaware_level}' "
                        "is missing from awareness_levels"
                    )
            if self.covert_ops.theft is not None:
                th_cfg = self.covert_ops.theft
                for aid in (
                    *th_cfg.steal_action_ids,
                    *th_cfg.plant_action_ids,
                    *th_cfg.lockpick_action_ids,
                ):
                    if aid not in self.actions:
                        errors.append(f"CovertOps theft references unknown action '{aid}'")
            if self.covert_ops.disguise is not None:
                dg_cfg = self.covert_ops.disguise
                for aid in (*dg_cfg.disguise_action_ids, *dg_cfg.scrutiny_action_ids):
                    if aid not in self.actions:
                        errors.append(f"CovertOps disguise references unknown action '{aid}'")
                for cid in dg_cfg.disguised_condition_ids:
                    if cid not in self.conditions:
                        errors.append(f"CovertOps disguise references unknown condition '{cid}'")

        return errors

    def _validate_effect(self, effect: EffectSpec, owner: str, errors: list[str]) -> None:
        non_formula_effects = {
            "emit_message",
            "shift_form",
            "revert_form",
            "set_awareness",
            "apply_disguise",
            "reveal_disguise",
            "transfer_item",
            "mark_provenance",
        }
        if effect.kind not in non_formula_effects:
            try:
                parse_formula(effect.formula)
            except FormulaError as exc:
                errors.append(f"{owner} effect formula '{effect.target_key}': {exc.message}")
        if effect.kind == "shift_form" and effect.target_key not in self.forms:
            errors.append(f"{owner} shift_form references unknown form '{effect.target_key}'")
        elif (
            effect.kind == "revert_form"
            and effect.target_key
            and effect.target_key not in self.forms
        ):
            errors.append(f"{owner} revert_form references unknown form '{effect.target_key}'")
        elif (
            effect.kind == "set_awareness"
            and self.covert_ops is not None
            and self.covert_ops.stealth is not None
            and effect.target_key not in self.covert_ops.stealth.awareness_levels
        ):
            errors.append(f"{owner} set_awareness references unknown level '{effect.target_key}'")
