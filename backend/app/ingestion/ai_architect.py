"""Deterministic System Wizard, Pattern Injector, Formula Builder & Tier-B Co-Designer."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from app.ingestion.models import (
    BlockCategory,
    DiffStatus,
    IngestionStagingJob,
    SourceCitation,
    StagingBlockProposal,
    canonical_sha256,
)
from app.ruleset_vm import (
    ActionBlock,
    ConditionBlock,
    CovertOpsConfigBlock,
    CovertPillar,
    DeckSpec,
    DisguisePillarConfig,
    EffectSpec,
    FlowConfig,
    FormBlock,
    FormulaExplanation,
    OutcomeTier,
    PackageManifest,
    PropertyBlock,
    RandomizerSpec,
    ResolutionMechanicBlock,
    ResourcePoolBlock,
    RulesetSchema,
    StealthPillarConfig,
    TheftPillarConfig,
    explain_ast_deterministically,
    parse_formula,
)

WizardParadigm = Literal[
    "roll_over",
    "roll_under",
    "tiered_2d6",
    "dice_pool",
    "step_dice",
    "card_draw",
    "coin_flip",
    "diceless",
]
WizardFlowMode = Literal["freeform", "round_initiative", "popcorn_spotlight"]
CreationParadigmChoice = Literal[
    "point_buy",
    "standard_array",
    "random_roll",
    "package_pick",
    "lifepath",
]
ClauseOperator = Literal["==", "!=", ">", ">=", "<", "<=", "+", "-", "*", "/"]


class SystemWizardConfig(BaseModel):
    """Deterministic 5-step configuration used to scaffold a complete valid .rpgrules draft."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    package_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    paradigm: WizardParadigm = "tiered_2d6"
    core_properties: tuple[str, ...] = ("might", "agility", "cognition", "resolve")
    primary_pool_id: str = Field(default="vitality", min_length=1)
    secondary_pool_id: str | None = "focus"
    flow_mode: WizardFlowMode = "freeform"
    enable_reactions: bool = False
    creation_paradigm: CreationParadigmChoice = "point_buy"
    enable_forms: bool = False
    covert_pillars: tuple[CovertPillar, ...] = ()


class PatchOperation(BaseModel):
    """Single declarative add/modify/remove mutation proposed for a RulesetSchema."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    op: Literal["add_block", "modify_block", "remove_block"]
    block_category: BlockCategory
    block_key: str = Field(min_length=1)
    payload: dict[str, object] = Field(default_factory=dict)


class RulesetPatchSpec(BaseModel):
    """Grammar-constrained JSON patch emitted by AI Architect or Subsystem Pattern Injector."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    summary: str = Field(min_length=1)
    operations: tuple[PatchOperation, ...] = Field(min_length=1)
    warnings: tuple[str, ...] = ()


class ArchitectPatchResult(BaseModel):
    """Validated ruleset modification result paired with diff staging proposals."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    base_hash: str
    proposed_ruleset: RulesetSchema
    patch: RulesetPatchSpec
    staging_job: IngestionStagingJob
    impacted_keys: tuple[str, ...] = ()
    validation_errors: tuple[str, ...] = ()


class FormulaClause(BaseModel):
    """Visual clause node compiled into a safe AST formula without writing raw syntax."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    left: str = Field(min_length=1)
    operator: ClauseOperator
    right: str = Field(min_length=1)


class RulesetSignatureHeader(BaseModel):
    """Compact ~500-token structural summary sent to Tier-B scoped block-slice prompts."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    package_id: str
    property_ids: tuple[str, ...] = ()
    pool_ids: tuple[str, ...] = ()
    resolution_ids: tuple[str, ...] = ()
    declared_primitives: tuple[str, ...] = ()
    estimated_tokens: int = Field(ge=1)


class ScopedArchitectPrompt(BaseModel):
    """Bounded Tier-B prompt slicing only relevant blocks rather than full manifests."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    signature: RulesetSignatureHeader
    included_block_keys: tuple[str, ...] = ()
    prompt_text: str
    estimated_tokens: int = Field(ge=1)


class SubsystemPatternInfo(BaseModel):
    """Metadata describing a deterministic 1-click subsystem macro injector."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    pattern_id: str
    label: str
    description: str
    default_params: dict[str, str | int] = Field(default_factory=dict)


SUBSYSTEM_PATTERNS: tuple[SubsystemPatternInfo, ...] = (
    SubsystemPatternInfo(
        pattern_id="stress_trauma_track",
        label="Stress & Trauma Track",
        description="Adds a segmented stress track plus an overstress trauma condition & hook.",
        default_params={"max_stress": 9, "condition_id": "shaken_nerves"},
    ),
    SubsystemPatternInfo(
        pattern_id="flat_mitigation_armor",
        label="Flat Mitigation & Wear",
        description="Adds flat guard mitigation property and a degraded armor condition.",
        default_params={"mitigation_value": 2},
    ),
    SubsystemPatternInfo(
        pattern_id="wound_thresholds",
        label="Severe Wound Thresholds",
        description="Adds major/critical wound threshold properties and bleeding condition.",
        default_params={"major_threshold": 6},
    ),
    SubsystemPatternInfo(
        pattern_id="threat_doom_clock",
        label="Threat Doom Clock Action",
        description="Adds an escalation strike action advancing a scene threat progress clock.",
        default_params={"clock_key": "doom_clock"},
    ),
    SubsystemPatternInfo(
        pattern_id="alternate_form_pack",
        label="Alternate Transformation Form",
        description="Adds an alternate FormBlock and declarative shift_form activation action.",
        default_params={"form_id": "shadow_aspect", "boost_prop": "might", "boost_val": 16},
    ),
    SubsystemPatternInfo(
        pattern_id="covert_ops_pack",
        label="3-Pillar Covert Operations",
        description="Enables stealth, theft, and disguise CovertOpsConfigBlock bindings.",
        default_params={"notice_delay_turns": 2},
    ),
    SubsystemPatternInfo(
        pattern_id="coin_flip_fate",
        label="Tossed Coin Destiny Resolution",
        description="Adds a binary coin_flip resolution mechanic and invoke action.",
        default_params={"mech_id": "fate_flip"},
    ),
)


def list_subsystem_patterns() -> tuple[SubsystemPatternInfo, ...]:
    """Return available zero-AI subsystem macro patterns."""
    return SUBSYSTEM_PATTERNS


def _default_stat_for_paradigm(paradigm: WizardParadigm) -> int:
    if paradigm in {"roll_over", "step_dice"}:
        return 12
    if paradigm == "roll_under":
        return 55
    if paradigm in {"tiered_2d6", "dice_pool", "diceless"}:
        return 2
    return 1


def _build_wizard_resolution(
    paradigm: WizardParadigm,
    lead_prop: str,
    primary_pool_id: str,
) -> tuple[ResolutionMechanicBlock, dict[str, DeckSpec]]:
    decks: dict[str, DeckSpec] = {}
    dmg_effect = (
        EffectSpec(
            kind="modify_pool",
            target_scope="target",
            target_key=primary_pool_id,
            formula="-4",
        ),
    )
    partial_effect = (
        EffectSpec(
            kind="modify_pool",
            target_scope="target",
            target_key=primary_pool_id,
            formula="-2",
        ),
    )
    miss_effect = (
        EffectSpec(
            kind="advance_clock",
            target_scope="scene",
            target_key="danger_clock",
            formula="1",
        ),
    )

    if paradigm == "roll_over":
        return (
            ResolutionMechanicBlock(
                mech_id="core_check",
                label="Core Roll-Over Check",
                randomizer=RandomizerSpec(kind="dice_formula", formula="1d20"),
                modifier_formula=f"floor((@self.{lead_prop} - 10) / 2)",
                target_formula="12",
                tiers=(
                    OutcomeTier(
                        tier_id="crit_success",
                        label="Critical Success",
                        condition="@roll.total >= 20",
                        effects=dmg_effect,
                    ),
                    OutcomeTier(
                        tier_id="success",
                        label="Success",
                        condition="@roll.total >= @roll.target",
                        effects=dmg_effect,
                    ),
                    OutcomeTier(
                        tier_id="miss",
                        label="Miss",
                        condition="true",
                        effects=miss_effect,
                    ),
                ),
            ),
            decks,
        )

    if paradigm == "roll_under":
        return (
            ResolutionMechanicBlock(
                mech_id="core_check",
                label="Percentile Roll-Under Check",
                randomizer=RandomizerSpec(kind="dice_formula", formula="1d100"),
                target_formula=f"@self.{lead_prop}",
                tiers=(
                    OutcomeTier(
                        tier_id="hard_success",
                        label="Hard Success",
                        condition="@roll.total <= floor(@roll.target / 2)",
                        effects=dmg_effect,
                    ),
                    OutcomeTier(
                        tier_id="regular_success",
                        label="Regular Success",
                        condition="@roll.total <= @roll.target",
                        effects=partial_effect,
                    ),
                    OutcomeTier(
                        tier_id="miss",
                        label="Fail",
                        condition="true",
                        effects=miss_effect,
                    ),
                ),
            ),
            decks,
        )

    if paradigm == "dice_pool":
        return (
            ResolutionMechanicBlock(
                mech_id="core_check",
                label="Success-Counting Dice Pool",
                randomizer=RandomizerSpec(
                    kind="dice_pool",
                    pool_size_formula=f"@self.{lead_prop} + 2",
                    die_sides=6,
                    success_threshold=5,
                ),
                tiers=(
                    OutcomeTier(
                        tier_id="strong_hit",
                        label="Strong Hits",
                        condition="@roll.hits >= 2",
                        effects=dmg_effect,
                    ),
                    OutcomeTier(
                        tier_id="hit",
                        label="Single Hit",
                        condition="@roll.hits >= 1",
                        effects=partial_effect,
                    ),
                    OutcomeTier(
                        tier_id="glitch_or_miss",
                        label="Miss",
                        condition="true",
                        effects=miss_effect,
                    ),
                ),
            ),
            decks,
        )

    if paradigm == "step_dice":
        return (
            ResolutionMechanicBlock(
                mech_id="core_check",
                label="Polyhedral Step-Die Check",
                randomizer=RandomizerSpec(
                    kind="step_dice",
                    step_die_formula="d8",
                    wild_die_sides=6,
                    explode=True,
                ),
                target_formula="4",
                tiers=(
                    OutcomeTier(
                        tier_id="raise",
                        label="Raise",
                        condition="@roll.total >= 8",
                        effects=dmg_effect,
                    ),
                    OutcomeTier(
                        tier_id="success",
                        label="Success",
                        condition="@roll.total >= 4",
                        effects=partial_effect,
                    ),
                    OutcomeTier(
                        tier_id="fail",
                        label="Fail",
                        condition="true",
                        effects=miss_effect,
                    ),
                ),
            ),
            decks,
        )

    if paradigm == "card_draw":
        deck_id = "fate_deck"
        decks[deck_id] = DeckSpec(
            deck_id=deck_id,
            label="Fate Draw Deck",
            scope="table_shared",
            cards=("zero", "plus_one", "plus_two", "minus_one", "triumph"),
            card_values={
                "zero": 0,
                "plus_one": 1,
                "plus_two": 2,
                "minus_one": -1,
                "triumph": 3,
            },
        )
        return (
            ResolutionMechanicBlock(
                mech_id="core_check",
                label="Fate Card Draw Check",
                randomizer=RandomizerSpec(kind="card_deck", deck_id=deck_id, draw_count=1),
                modifier_formula=f"@self.{lead_prop}",
                target_formula="2",
                tiers=(
                    OutcomeTier(
                        tier_id="success",
                        label="Favorable Draw",
                        condition="@roll.total >= @roll.target",
                        effects=dmg_effect,
                    ),
                    OutcomeTier(
                        tier_id="setback",
                        label="Setback",
                        condition="true",
                        effects=miss_effect,
                    ),
                ),
            ),
            decks,
        )

    if paradigm == "coin_flip":
        return (
            ResolutionMechanicBlock(
                mech_id="core_check",
                label="Coin Toss Resolution",
                randomizer=RandomizerSpec(kind="coin_flip", pool_size_formula="3"),
                tiers=(
                    OutcomeTier(
                        tier_id="favorable",
                        label="Favorable Odds",
                        condition="@roll.heads >= 2",
                        effects=dmg_effect,
                    ),
                    OutcomeTier(
                        tier_id="mixed",
                        label="Mixed Toss",
                        condition="@roll.heads == 1",
                        effects=partial_effect,
                    ),
                    OutcomeTier(
                        tier_id="miss",
                        label="All Tails",
                        condition="true",
                        effects=miss_effect,
                    ),
                ),
            ),
            decks,
        )

    if paradigm == "diceless":
        return (
            ResolutionMechanicBlock(
                mech_id="core_check",
                label="Diceless Trait Comparison",
                randomizer=RandomizerSpec(kind="none", base_value=0),
                modifier_formula=f"@self.{lead_prop}",
                target_formula="1",
                tiers=(
                    OutcomeTier(
                        tier_id="prevail",
                        label="Prevail",
                        condition="@roll.total >= @roll.target",
                        effects=partial_effect,
                    ),
                    OutcomeTier(
                        tier_id="complication",
                        label="Complication",
                        condition="true",
                        effects=miss_effect,
                    ),
                ),
            ),
            decks,
        )

    # Default: tiered_2d6
    return (
        ResolutionMechanicBlock(
            mech_id="core_check",
            label="2d6 Tiered Resolution",
            randomizer=RandomizerSpec(kind="dice_formula", formula="2d6"),
            modifier_formula=f"@self.{lead_prop}",
            tiers=(
                OutcomeTier(
                    tier_id="strong_hit",
                    label="Full Success (10+)",
                    condition="@roll.total >= 10",
                    effects=dmg_effect,
                ),
                OutcomeTier(
                    tier_id="weak_hit",
                    label="Mixed Success (7-9)",
                    condition="@roll.total >= 7",
                    effects=partial_effect,
                ),
                OutcomeTier(
                    tier_id="miss",
                    label="Miss (<=6)",
                    condition="true",
                    effects=miss_effect,
                ),
            ),
        ),
        decks,
    )


def run_deterministic_system_wizard(
    config: SystemWizardConfig,
) -> tuple[RulesetSchema, IngestionStagingJob]:
    """Compile a 5-step wizard specification into a validated RulesetSchema & staging job."""
    if not config.core_properties:
        raise ValueError("core_properties must contain at least one property.")

    default_val = _default_stat_for_paradigm(config.paradigm)
    lead_prop = config.core_properties[0]
    props: dict[str, PropertyBlock] = {
        pid: PropertyBlock(
            prop_id=pid,
            label=pid.replace("_", " ").title(),
            default_value=default_val,
        )
        for pid in config.core_properties
    }
    props["guard"] = PropertyBlock(
        prop_id="guard",
        label="Guard Defense",
        formula=f"@self.{lead_prop}",
        category="derived",
    )

    pools: dict[str, ResourcePoolBlock] = {
        config.primary_pool_id: ResourcePoolBlock(
            pool_id=config.primary_pool_id,
            label=config.primary_pool_id.replace("_", " ").title(),
            default_current=20,
            max_formula="20",
            min_value=0,
        )
    }
    if config.secondary_pool_id and config.secondary_pool_id != config.primary_pool_id:
        pools[config.secondary_pool_id] = ResourcePoolBlock(
            pool_id=config.secondary_pool_id,
            label=config.secondary_pool_id.replace("_", " ").title(),
            default_current=6,
            max_formula="10",
            min_value=0,
            reset_on="rest",
        )

    core_mech, decks = _build_wizard_resolution(config.paradigm, lead_prop, config.primary_pool_id)
    actions: dict[str, ActionBlock] = {
        "strike": ActionBlock(
            action_id="strike",
            label="Signature Strike",
            category="action",
            resolution_id="core_check",
            requires_target=True,
            allow_reactions=config.enable_reactions,
        )
    }
    if config.enable_reactions:
        actions["parry_reaction"] = ActionBlock(
            action_id="parry_reaction",
            label="Deflect / Parry",
            category="reaction",
            trigger="on_targeted",
            default_effects=(
                EffectSpec(
                    kind="advance_clock",
                    target_scope="scene",
                    target_key="parried_hits",
                    formula="1",
                ),
            ),
        )

    conditions: dict[str, ConditionBlock] = {
        "off_balance": ConditionBlock(
            condition_id="off_balance",
            label="Off Balance",
            description="Temporarily compromised stance.",
            property_modifiers={lead_prop: "-1"},
            default_duration_turns=1,
        )
    }
    forms: dict[str, FormBlock] = {}
    if config.enable_forms:
        forms["feral_aspect"] = FormBlock(
            form_id="feral_aspect",
            label="Feral Aspect",
            property_mode="delta_overlay",
            property_deltas={lead_prop: "2"},
            granted_tags=("transformed",),
        )
        actions["assume_feral"] = ActionBlock(
            action_id="assume_feral",
            label="Assume Feral Aspect",
            category="power",
            default_effects=(
                EffectSpec(kind="shift_form", target_scope="self", target_key="feral_aspect"),
            ),
        )

    covert_ops: CovertOpsConfigBlock | None = None
    if config.covert_pillars:
        pillar_set = set(config.covert_pillars)
        covert_ops = CovertOpsConfigBlock(
            stealth=StealthPillarConfig() if "stealth" in pillar_set else None,
            theft=TheftPillarConfig() if "theft" in pillar_set else None,
            disguise=DisguisePillarConfig() if "disguise" in pillar_set else None,
        )

    declared: list[str] = ["resolution_mechanic", config.creation_paradigm]
    if config.flow_mode == "round_initiative":
        declared.append("spatial_grid")
    if config.enable_forms:
        declared.append("forms")
    for p in config.covert_pillars:
        declared.append(f"covert_{p}")

    ruleset = RulesetSchema(
        manifest=PackageManifest(
            package_type="ruleset",
            package_id=config.package_id,
            name=config.name,
            version="0.1.0",
        ),
        declared_primitives=tuple(dict.fromkeys(declared)),
        properties=props,
        resource_pools=pools,
        resolutions={"core_check": core_mech},
        conditions=conditions,
        actions=actions,
        decks=decks,
        forms=forms,
        flow_config=FlowConfig(default_mode=config.flow_mode),
        covert_ops=covert_ops,
    )
    errors = ruleset.validate_graph()
    if errors:
        raise ValueError("; ".join(errors))

    cit = SourceCitation(
        source_name=f"wizard:{config.package_id}",
        source_kind="json",
        anchor="system_wizard",
        excerpt=f"Generated {config.paradigm} draft ruleset via 5-step deterministic wizard.",
    )
    proposals: list[StagingBlockProposal] = []
    for pid, pblock in sorted(props.items()):
        pl = cast(dict[str, object], pblock.model_dump(mode="json"))
        proposals.append(
            StagingBlockProposal(
                proposal_id=f"wiz_prop_{pid}",
                block_category="property",
                block_key=pid,
                proposed_payload=pl,
                source_citation=cit,
            )
        )
    for pool_id, rpool in sorted(pools.items()):
        pl = cast(dict[str, object], rpool.model_dump(mode="json"))
        proposals.append(
            StagingBlockProposal(
                proposal_id=f"wiz_pool_{pool_id}",
                block_category="resource_pool",
                block_key=pool_id,
                proposed_payload=pl,
                source_citation=cit,
            )
        )
    proposals.append(
        StagingBlockProposal(
            proposal_id="wiz_res_core_check",
            block_category="resolution",
            block_key="core_check",
            proposed_payload=cast(dict[str, object], core_mech.model_dump(mode="json")),
            source_citation=cit,
        )
    )
    for aid, act in sorted(actions.items()):
        proposals.append(
            StagingBlockProposal(
                proposal_id=f"wiz_act_{aid}",
                block_category="action",
                block_key=aid,
                proposed_payload=cast(dict[str, object], act.model_dump(mode="json")),
                source_citation=cit,
            )
        )
    job = IngestionStagingJob(
        job_id=f"wiz_{canonical_sha256(ruleset.content_hash())[:12]}",
        source_name=f"wizard:{config.package_id}",
        source_kind="json",
        status="ready_for_review",
        proposals=tuple(proposals),
    )
    return ruleset, job


def build_formula_from_clauses(
    clauses: Sequence[FormulaClause],
    *,
    combine_op: Literal["&&", "||", "+"] = "&&",
) -> str:
    """Compile structured UI formula clauses into a validated deterministic AST string."""
    if not clauses:
        raise ValueError("At least one FormulaClause is required.")
    rendered: list[str] = []
    for clause in clauses:
        expr = f"{clause.left.strip()} {clause.operator} {clause.right.strip()}"
        parse_formula(expr)
        rendered.append(f"({expr})" if len(clauses) > 1 else expr)
    combined = f" {combine_op} ".join(rendered)
    parse_formula(combined)
    return combined


def explain_ruleset_formula(
    formula: str,
    sample_context: Mapping[str, object],
) -> FormulaExplanation:
    """Explain any AST formula deterministically using sample character attributes (0 AI calls)."""
    return explain_ast_deterministically(formula, sample_context)


def build_scoped_block_slice_prompt(
    ruleset: RulesetSchema,
    user_request: str,
    *,
    max_blocks: int = 8,
    max_tokens: int = 6000,
) -> ScopedArchitectPrompt:
    """Assemble a ~500-token signature + 3-8 relevant blocks (never full ruleset JSON)."""
    sig_est = max(
        1,
        len(ruleset.properties) * 4
        + len(ruleset.resource_pools) * 4
        + len(ruleset.resolutions) * 5
        + 40,
    )
    signature = RulesetSignatureHeader(
        package_id=ruleset.manifest.package_id,
        property_ids=tuple(sorted(ruleset.properties)),
        pool_ids=tuple(sorted(ruleset.resource_pools)),
        resolution_ids=tuple(sorted(ruleset.resolutions)),
        declared_primitives=ruleset.declared_primitives,
        estimated_tokens=sig_est,
    )

    tokens = {tok.strip(",.?!:;\"'()").lower() for tok in user_request.split() if len(tok) >= 3}
    candidates: list[tuple[int, str, str, object]] = []

    def _score_block(cat: str, key: str, model: BaseModel) -> None:
        raw_text = json_dump_compact(model).lower()
        score = 0
        if key.lower() in tokens:
            score += 5
        for t in tokens:
            if t in key.lower():
                score += 3
            elif t in raw_text:
                score += 1
        candidates.append((score, cat, key, model.model_dump(mode="json")))

    for k, m in sorted(ruleset.properties.items()):
        _score_block("property", k, m)
    for k, m in sorted(ruleset.resource_pools.items()):
        _score_block("resource_pool", k, m)
    for k, m in sorted(ruleset.resolutions.items()):
        _score_block("resolution", k, m)
    for k, m in sorted(ruleset.conditions.items()):
        _score_block("condition", k, m)
    for k, m in sorted(ruleset.actions.items()):
        _score_block("action", k, m)
    for k, m in sorted(ruleset.event_hooks.items()):
        _score_block("event_hook", k, m)
    for k, m in sorted(ruleset.forms.items()):
        _score_block("form", k, m)
    if ruleset.covert_ops is not None:
        _score_block("covert_ops", "covert_ops", ruleset.covert_ops)

    candidates.sort(key=lambda item: (-item[0], item[1], item[2]))
    selected = candidates[: max(1, min(max_blocks, len(candidates)))]

    lines = [
        f"RULESET_SIGNATURE: {signature.model_dump_json()}",
        f"REQUEST: {user_request.strip()}",
        "REFERENCED_BLOCKS:",
    ]
    included_keys: list[str] = []
    max_chars = max_tokens * 4
    for _, cat, key, payload in selected:
        entry_line = f"- [{cat}:{key}] {json_dump_compact(payload)}"
        if sum(len(ln) for ln in lines) + len(entry_line) > max_chars and included_keys:
            break
        lines.append(entry_line)
        included_keys.append(f"{cat}:{key}")

    prompt_text = "\n".join(lines)
    est_tokens = max(1, (len(prompt_text) + 3) // 4)
    return ScopedArchitectPrompt(
        signature=signature,
        included_block_keys=tuple(included_keys),
        prompt_text=prompt_text,
        estimated_tokens=est_tokens,
    )


def json_dump_compact(obj: object) -> str:
    """Serialize Pydantic models or dicts compactly for token estimation."""
    if isinstance(obj, BaseModel):
        data: object = obj.model_dump(mode="json")
    else:
        data = obj
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def _existing_block_payload(
    ruleset: RulesetSchema,
    category: BlockCategory,
    key: str,
) -> dict[str, object] | None:
    model_obj: BaseModel | None = None
    if category == "property":
        model_obj = ruleset.properties.get(key)
    elif category == "resource_pool":
        model_obj = ruleset.resource_pools.get(key)
    elif category == "resolution":
        model_obj = ruleset.resolutions.get(key)
    elif category == "condition":
        model_obj = ruleset.conditions.get(key)
    elif category == "action":
        model_obj = ruleset.actions.get(key)
    elif category == "event_hook":
        model_obj = ruleset.event_hooks.get(key)
    elif category == "deck":
        model_obj = ruleset.decks.get(key)
    elif category == "form":
        model_obj = ruleset.forms.get(key)
    elif category == "covert_ops":
        model_obj = ruleset.covert_ops
    elif category == "flow_config":
        model_obj = ruleset.flow_config
    elif category == "manifest":
        model_obj = ruleset.manifest
    return (
        cast(dict[str, object], model_obj.model_dump(mode="json"))
        if model_obj is not None
        else None
    )


def apply_ruleset_patch(
    base_ruleset: RulesetSchema,
    patch: RulesetPatchSpec,
    *,
    source_name: str = "ai_architect",
) -> ArchitectPatchResult:
    """Apply a declarative RulesetPatchSpec, validate graph invariants, and stage diffs."""
    data = cast(dict[str, object], base_ruleset.model_dump(mode="json"))
    map_field_by_cat: dict[BlockCategory, str] = {
        "property": "properties",
        "resource_pool": "resource_pools",
        "resolution": "resolutions",
        "condition": "conditions",
        "action": "actions",
        "event_hook": "event_hooks",
        "deck": "decks",
        "form": "forms",
    }

    proposals: list[StagingBlockProposal] = []
    impacted: set[str] = set()
    cit = SourceCitation(
        source_name=source_name,
        source_kind="json",
        anchor="ruleset_patch",
        excerpt=patch.summary[:220],
    )

    for op in patch.operations:
        existing_before = _existing_block_payload(base_ruleset, op.block_category, op.block_key)
        impacted.add(f"{op.block_category}:{op.block_key}")

        if op.block_category in map_field_by_cat:
            field_name = map_field_by_cat[op.block_category]
            bucket = cast(dict[str, object], dict(cast(Mapping[str, object], data[field_name])))
            if op.op == "remove_block":
                bucket.pop(op.block_key, None)
                diff_st: DiffStatus = "MODIFIED"
                final_payload: dict[str, object] = {}
            else:
                merged = dict(existing_before or {}) if op.op == "modify_block" else {}
                merged.update(op.payload)
                bucket[op.block_key] = merged
                final_payload = merged
                diff_st = "NEW" if existing_before is None else "MODIFIED"
            data[field_name] = bucket
        elif op.block_category == "covert_ops":
            if op.op == "remove_block":
                data["covert_ops"] = None
                final_payload = {}
            else:
                merged = dict(existing_before or {}) if op.op == "modify_block" else {}
                merged.update(op.payload)
                data["covert_ops"] = merged
                final_payload = merged
            diff_st = "NEW" if existing_before is None else "MODIFIED"
        elif op.block_category in {"flow_config", "manifest"}:
            merged = dict(existing_before or {})
            merged.update(op.payload)
            data[op.block_category] = merged
            final_payload = merged
            diff_st = "MODIFIED"
        else:
            raise ValueError(f"Unsupported patch block_category '{op.block_category}'.")

        proposals.append(
            StagingBlockProposal(
                proposal_id=f"patch_{op.block_category}_{op.block_key}_{canonical_sha256(op.model_dump(mode='json'))[:10]}",
                block_category=op.block_category,
                block_key=op.block_key,
                proposed_payload=final_payload,
                confidence_score=0.95,
                source_citation=cit,
                diff_status=diff_st,
                existing_payload=existing_before,
                notes=f"{op.op} via {patch.summary}",
            )
        )

    proposed = RulesetSchema.model_validate(data)
    errors = tuple(proposed.validate_graph())
    job = IngestionStagingJob(
        job_id=f"arch_{canonical_sha256((base_ruleset.content_hash(), patch.summary))[:12]}",
        source_name=source_name,
        source_kind="json",
        status="ready_for_review" if not errors else "failed",
        proposals=tuple(proposals),
        warnings=patch.warnings,
    )
    return ArchitectPatchResult(
        base_hash=base_ruleset.content_hash(),
        proposed_ruleset=proposed,
        patch=patch,
        staging_job=job,
        impacted_keys=tuple(sorted(impacted)),
        validation_errors=errors,
    )


def inject_subsystem_pattern(
    ruleset: RulesetSchema,
    pattern_id: str,
    params: Mapping[str, object] | None = None,
) -> ArchitectPatchResult:
    """Inject a validated deterministic subsystem macro into an existing RulesetSchema."""
    cfg = dict(params or {})
    ops: list[PatchOperation] = []

    if pattern_id == "stress_trauma_track":
        max_stress = int(str(cfg.get("max_stress", 9)))
        cond_id = str(cfg.get("condition_id", "shaken_nerves"))
        ops = [
            PatchOperation(
                op="add_block",
                block_category="resource_pool",
                block_key="stress",
                payload={
                    "pool_id": "stress",
                    "label": "Stress",
                    "default_current": 0,
                    "max_formula": str(max_stress),
                    "min_value": 0,
                    "track_segments": max_stress,
                },
            ),
            PatchOperation(
                op="add_block",
                block_category="condition",
                block_key=cond_id,
                payload={
                    "condition_id": cond_id,
                    "label": cond_id.replace("_", " ").title(),
                    "description": "Triggered when stress reaches capacity.",
                    "persistent_flag": True,
                },
            ),
            PatchOperation(
                op="add_block",
                block_category="event_hook",
                block_key="stress_overflow_hook",
                payload={
                    "hook_id": "stress_overflow_hook",
                    "event_name": "on_action_resolved",
                    "condition": f"@self.stress >= {max_stress}",
                    "effects": [
                        {
                            "kind": "add_condition",
                            "target_scope": "self",
                            "target_key": cond_id,
                        }
                    ],
                },
            ),
        ]
        summary = "Inject Stress & Trauma segmented track"
    elif pattern_id == "flat_mitigation_armor":
        mit = int(str(cfg.get("mitigation_value", 2)))
        ops = [
            PatchOperation(
                op="add_block",
                block_category="property",
                block_key="damage_mitigation",
                payload={
                    "prop_id": "damage_mitigation",
                    "label": "Flat Mitigation",
                    "default_value": mit,
                    "min_value": 0,
                },
            ),
            PatchOperation(
                op="add_block",
                block_category="condition",
                block_key="armor_frayed",
                payload={
                    "condition_id": "armor_frayed",
                    "label": "Frayed Armor",
                    "property_modifiers": {"damage_mitigation": "-1"},
                },
            ),
        ]
        summary = "Inject flat damage mitigation & frayed armor condition"
    elif pattern_id == "wound_thresholds":
        thresh = int(str(cfg.get("major_threshold", 6)))
        ops = [
            PatchOperation(
                op="add_block",
                block_category="property",
                block_key="major_wound_threshold",
                payload={
                    "prop_id": "major_wound_threshold",
                    "label": "Major Wound Threshold",
                    "default_value": thresh,
                    "min_value": 1,
                },
            ),
            PatchOperation(
                op="add_block",
                block_category="condition",
                block_key="bleeding_wound",
                payload={
                    "condition_id": "bleeding_wound",
                    "label": "Bleeding Wound",
                    "persistent_flag": True,
                },
            ),
        ]
        summary = "Inject wound threshold property and bleeding condition"
    elif pattern_id == "threat_doom_clock":
        clock_key = str(cfg.get("clock_key", "doom_clock"))
        ops = [
            PatchOperation(
                op="add_block",
                block_category="action",
                block_key="tick_threat_clock",
                payload={
                    "action_id": "tick_threat_clock",
                    "label": "Escalate Threat Clock",
                    "category": "action",
                    "default_effects": [
                        {
                            "kind": "advance_clock",
                            "target_scope": "scene",
                            "target_key": clock_key,
                            "formula": "1",
                        }
                    ],
                },
            )
        ]
        summary = f"Inject threat clock escalation action for '{clock_key}'"
    elif pattern_id == "alternate_form_pack":
        fid = str(cfg.get("form_id", "shadow_aspect"))
        target_prop = str(
            cfg.get("boost_prop") or next(iter(sorted(ruleset.properties)), "resolve")
        )
        ops = [
            PatchOperation(
                op="add_block",
                block_category="form",
                block_key=fid,
                payload={
                    "form_id": fid,
                    "label": fid.replace("_", " ").title(),
                    "property_mode": "delta_overlay",
                    "property_deltas": (
                        {target_prop: "2"} if target_prop in ruleset.properties else {}
                    ),
                    "granted_tags": ["transformed"],
                },
            ),
            PatchOperation(
                op="add_block",
                block_category="action",
                block_key=f"shift_{fid}",
                payload={
                    "action_id": f"shift_{fid}",
                    "label": f"Shift into {fid.replace('_', ' ').title()}",
                    "category": "power",
                    "default_effects": [
                        {
                            "kind": "shift_form",
                            "target_scope": "self",
                            "target_key": fid,
                        }
                    ],
                },
            ),
        ]
        summary = f"Inject Alternate Form '{fid}' & transformation action"
    elif pattern_id == "covert_ops_pack":
        delay = int(str(cfg.get("notice_delay_turns", 2)))
        ops = [
            PatchOperation(
                op="add_block",
                block_category="covert_ops",
                block_key="covert_ops",
                payload={
                    "stealth": {},
                    "theft": {"default_notice_delay_turns": max(1, delay)},
                    "disguise": {},
                },
            )
        ]
        summary = "Inject 3-pillar CovertOpsConfigBlock bindings"
    elif pattern_id == "coin_flip_fate":
        mid = str(cfg.get("mech_id", "fate_flip"))
        ops = [
            PatchOperation(
                op="add_block",
                block_category="resolution",
                block_key=mid,
                payload={
                    "mech_id": mid,
                    "label": "Coin Toss Destiny",
                    "randomizer": {"kind": "coin_flip", "pool_size_formula": "1"},
                    "tiers": [
                        {
                            "tier_id": "heads",
                            "label": "Heads Prevails",
                            "condition": "@roll.heads >= 1",
                            "effects": [
                                {
                                    "kind": "advance_clock",
                                    "target_scope": "scene",
                                    "target_key": "fortune",
                                    "formula": "1",
                                }
                            ],
                        },
                        {"tier_id": "tails", "label": "Tails", "condition": "true", "effects": []},
                    ],
                },
            ),
            PatchOperation(
                op="add_block",
                block_category="action",
                block_key=f"invoke_{mid}",
                payload={
                    "action_id": f"invoke_{mid}",
                    "label": "Flip Fate Coin",
                    "category": "action",
                    "resolution_id": mid,
                },
            ),
        ]
        summary = "Inject binary coin_flip resolution mechanic & invoke action"
    else:
        raise KeyError(f"Unknown subsystem pattern '{pattern_id}'.")

    return apply_ruleset_patch(
        ruleset,
        RulesetPatchSpec(summary=summary, operations=tuple(ops)),
        source_name=f"pattern:{pattern_id}",
    )


def run_ai_architect_request(
    ruleset: RulesetSchema,
    user_request: str,
    *,
    llm_patch_fn: Callable[[ScopedArchitectPrompt], Mapping[str, object] | RulesetPatchSpec],
    max_blocks: int = 8,
    max_tokens: int = 6000,
) -> ArchitectPatchResult:
    """Assemble scoped Tier-B prompt, validate emitted JSON patch, and stage diff."""
    scoped = build_scoped_block_slice_prompt(
        ruleset,
        user_request,
        max_blocks=max_blocks,
        max_tokens=max_tokens,
    )
    raw = llm_patch_fn(scoped)
    patch = raw if isinstance(raw, RulesetPatchSpec) else RulesetPatchSpec.model_validate(raw)
    return apply_ruleset_patch(ruleset, patch, source_name="ai_architect_tier_b")
