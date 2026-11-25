"""Probability Curve Analyzer, Static Ruleset Linter & Headless Monte Carlo TTK Sandbox."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.ingestion.models import MODULE_MANIFEST as INGESTION_MODULE_MANIFEST
from app.ruleset_vm import (
    COVERT_OPS_MODULE_MANIFEST,
    TIME_SKIP_MODULE_MANIFEST,
    EntityState,
    FormulaError,
    MeddahModuleManifest,
    ModuleRegistry,
    RulesetSchema,
    compute_entity_view,
    execute_action,
    extract_references,
    initialize_scene_state,
    parse_formula,
    resolve_randomizer,
)
from app.ruleset_vm.rng import DeterministicRngStream


class ProbabilityPoint(BaseModel):
    """Empirical probability breakdown for a resolution mechanic at one modifier step."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    modifier_value: int | float
    samples: int = Field(ge=1)
    mean_total: float
    min_total: int | float
    max_total: int | float
    tier_probabilities: dict[str, float] = Field(default_factory=dict)
    glitch_rate: float = 0.0


class ProbabilityCurveReport(BaseModel):
    """Probability curve sweep across modifier values using DeterministicRngStream."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mech_id: str
    label: str
    target_value: int | float | None = None
    points: tuple[ProbabilityPoint, ...] = ()
    seed: str


class LinterDiagnostic(BaseModel):
    """Single static diagnostic reported by the ruleset dependency & sanity linter."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    severity: Literal["error", "warning", "info"]
    code: str = Field(min_length=1)
    block_key: str = Field(min_length=1)
    message: str = Field(min_length=1)


class ModuleReadinessItem(BaseModel):
    """§1.0 module activation readiness summary for a RulesetSchema."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    module_id: str
    state: Literal["dormant", "available", "active"]
    missing_primitives: tuple[str, ...] = ()


class RulesetLintReport(BaseModel):
    """Complete static verification and §1.0 module readiness report for a RulesetSchema."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    is_valid: bool
    diagnostics: tuple[LinterDiagnostic, ...] = ()
    module_readiness: tuple[ModuleReadinessItem, ...] = ()


class BalanceSimulationReport(BaseModel):
    """Headless deterministic combat/action TTK & deadlock report."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    trials_run: int = Field(ge=1)
    attacker_win_rate: float = Field(ge=0.0, le=1.0)
    defender_win_rate: float = Field(ge=0.0, le=1.0)
    stalemate_rate: float = Field(ge=0.0, le=1.0)
    avg_ttk_rounds: float | None = None
    min_ttk_rounds: int | None = None
    max_ttk_rounds: int | None = None
    avg_attacker_pool_drain: float
    avg_defender_pool_drain: float
    deadlock_warnings: tuple[str, ...] = ()
    seed: str
    ruleset_hash: str


def analyze_resolution_probabilities(
    ruleset: RulesetSchema,
    mech_id: str,
    *,
    modifier_values: Sequence[int] = (0, 2, 4, 6),
    target_value: int | float | None = None,
    samples_per_point: int = 500,
    seed: str = "meddah-prob",
) -> ProbabilityCurveReport:
    """Compute exact seeded Monte Carlo probability distributions across modifier steps."""
    mech = ruleset.resolutions.get(mech_id)
    if mech is None:
        raise KeyError(f"Unknown resolution mechanic '{mech_id}'.")
    if samples_per_point < 1:
        raise ValueError("samples_per_point must be >= 1.")
    if not modifier_values:
        raise ValueError("modifier_values must not be empty.")

    sample_ent = EntityState(entity_id="sim_actor", name="Sim Actor")
    sample_ctx = compute_entity_view(ruleset, sample_ent).to_eval_context()
    eval_ctx: dict[str, object] = {"@self": sample_ctx, "@target": sample_ctx}

    points: list[ProbabilityPoint] = []
    for mod in modifier_values:
        rng = DeterministicRngStream(seed=f"{seed}:{mech_id}:{mod}", stream_name="prob")
        totals: list[int | float] = []
        tier_counts: dict[str, int] = {tier.tier_id: 0 for tier in mech.tiers}
        glitches = 0

        for _ in range(samples_per_point):
            roll, _ = resolve_randomizer(
                mech.randomizer,
                rng,
                eval_ctx,
                deck_specs=ruleset.decks,
                modifier_value=mod,
                target_value=target_value,
                tiers=mech.tiers,
            )
            totals.append(roll.total)
            if roll.tier_id is not None:
                tier_counts[roll.tier_id] = tier_counts.get(roll.tier_id, 0) + 1
            if roll.is_glitch:
                glitches += 1

        tier_probs = {
            tid: round(cnt / samples_per_point, 4) for tid, cnt in sorted(tier_counts.items())
        }
        points.append(
            ProbabilityPoint(
                modifier_value=mod,
                samples=samples_per_point,
                mean_total=round(sum(totals) / samples_per_point, 4),
                min_total=min(totals),
                max_total=max(totals),
                tier_probabilities=tier_probs,
                glitch_rate=round(glitches / samples_per_point, 4),
            )
        )

    return ProbabilityCurveReport(
        mech_id=mech_id,
        label=mech.label,
        target_value=target_value,
        points=tuple(points),
        seed=seed,
    )


def _check_ast_self_target_refs(
    formula: str,
    ruleset: RulesetSchema,
    owner: str,
    diagnostics: list[LinterDiagnostic],
) -> None:
    try:
        refs = extract_references(formula)
    except FormulaError as exc:
        diagnostics.append(
            LinterDiagnostic(
                severity="error", code="LINT-AST", block_key=owner, message=exc.message
            )
        )
        return
    known_entity_keys = (
        set(ruleset.properties)
        | set(ruleset.resource_pools)
        | {
            "entity_id",
            "name",
            "pools",
            "pool_maxes",
            "conditions",
            "tags",
            "blocked_tags",
            "active_form_id",
            "active_form_involuntary",
            "active_disguise_alias",
            "presented_name",
            "disguise_quality",
            "stealth_score",
            "granted_actions",
        }
    )
    for ref in refs:
        if ref.startswith("@self.") or ref.startswith("@target."):
            field = ref.split(".", 1)[1].split(".", 1)[0]
            if field not in known_entity_keys:
                diagnostics.append(
                    LinterDiagnostic(
                        severity="warning",
                        code="LINT-REF",
                        block_key=owner,
                        message=(
                            f"Formula '{formula}' references unknown entity attribute '{field}'."
                        ),
                    )
                )


def lint_ruleset_schema(
    ruleset: RulesetSchema,
    *,
    extra_manifests: Sequence[MeddahModuleManifest] = (),
) -> RulesetLintReport:
    """Run deep static validation, orphan detection, and §1.0 module readiness inspection."""
    diagnostics: list[LinterDiagnostic] = []

    for err in ruleset.validate_graph():
        diagnostics.append(
            LinterDiagnostic(severity="error", code="LINT-GRAPH", block_key="ruleset", message=err)
        )

    referenced_resolutions: set[str] = set()
    referenced_conditions: set[str] = set()

    for aid, act in sorted(ruleset.actions.items()):
        if act.resolution_id is not None:
            referenced_resolutions.add(act.resolution_id)
        _check_ast_self_target_refs(act.requires, ruleset, f"action:{aid}", diagnostics)
        for pool_id, cost_expr in sorted(act.pool_costs.items()):
            if pool_id not in ruleset.resource_pools:
                diagnostics.append(
                    LinterDiagnostic(
                        severity="error",
                        code="LINT-POOL",
                        block_key=f"action:{aid}",
                        message=f"pool_costs references unknown pool '{pool_id}'.",
                    )
                )
            else:
                try:
                    parse_formula(cost_expr)
                except FormulaError as exc:
                    diagnostics.append(
                        LinterDiagnostic(
                            severity="error",
                            code="LINT-AST",
                            block_key=f"action:{aid}",
                            message=f"Invalid pool_costs expression '{cost_expr}': {exc.message}",
                        )
                    )
        for eff in act.default_effects:
            if eff.kind in {"add_condition", "remove_condition"} and eff.target_key:
                referenced_conditions.add(eff.target_key)

    for mid, mech in sorted(ruleset.resolutions.items()):
        for tier in mech.tiers:
            _check_ast_self_target_refs(tier.condition, ruleset, f"resolution:{mid}", diagnostics)
            for eff in tier.effects:
                if eff.kind in {"add_condition", "remove_condition"} and eff.target_key:
                    referenced_conditions.add(eff.target_key)
        if mid not in referenced_resolutions:
            diagnostics.append(
                LinterDiagnostic(
                    severity="info",
                    code="LINT-ORPHAN",
                    block_key=f"resolution:{mid}",
                    message=f"Resolution '{mid}' is not linked to any ActionBlock.",
                )
            )

    for hk in sorted(ruleset.event_hooks.values(), key=lambda item: item.hook_id):
        _check_ast_self_target_refs(hk.condition, ruleset, f"hook:{hk.hook_id}", diagnostics)
        for eff in hk.effects:
            if eff.kind in {"add_condition", "remove_condition"} and eff.target_key:
                referenced_conditions.add(eff.target_key)

    if ruleset.covert_ops is not None:
        if ruleset.covert_ops.stealth is not None:
            referenced_conditions.update(ruleset.covert_ops.stealth.hidden_condition_ids)
        if ruleset.covert_ops.disguise is not None:
            referenced_conditions.update(ruleset.covert_ops.disguise.disguised_condition_ids)

    for cid in sorted(ruleset.conditions):
        if cid not in referenced_conditions:
            diagnostics.append(
                LinterDiagnostic(
                    severity="info",
                    code="LINT-ORPHAN",
                    block_key=f"condition:{cid}",
                    message=f"Condition '{cid}' is not emitted by any action, tier, or hook.",
                )
            )

    reg = ModuleRegistry()
    for manifest in (
        COVERT_OPS_MODULE_MANIFEST,
        TIME_SKIP_MODULE_MANIFEST,
        INGESTION_MODULE_MANIFEST,
        *extra_manifests,
    ):
        reg.register(manifest)

    snapshots = reg.resolve_all(ruleset.declared_primitives)
    readiness = tuple(
        ModuleReadinessItem(
            module_id=snap.module_id,
            state=snap.state,
            missing_primitives=snap.missing_primitives,
        )
        for snap in snapshots.values()
    )
    has_errors = any(d.severity == "error" for d in diagnostics)
    return RulesetLintReport(
        is_valid=not has_errors,
        diagnostics=tuple(diagnostics),
        module_readiness=readiness,
    )


def run_monte_carlo_simulation(
    ruleset: RulesetSchema,
    attacker: EntityState,
    defender: EntityState,
    *,
    attacker_action_id: str,
    defender_action_id: str | None = None,
    vitality_pool_id: str,
    trials: int = 200,
    max_rounds: int = 30,
    seed: str = "meddah-sim",
) -> BalanceSimulationReport:
    """Execute deterministic headless combat/action trials checking TTK and deadlocks."""
    if trials < 1:
        raise ValueError("trials must be >= 1.")
    if max_rounds < 1:
        raise ValueError("max_rounds must be >= 1.")
    if attacker_action_id not in ruleset.actions:
        raise KeyError(f"Unknown attacker_action_id '{attacker_action_id}'.")
    if defender_action_id is not None and defender_action_id not in ruleset.actions:
        raise KeyError(f"Unknown defender_action_id '{defender_action_id}'.")

    att_wins = 0
    def_wins = 0
    stalemates = 0
    ttk_rounds: list[int] = []
    att_drains: list[int] = []
    def_drains: list[int] = []

    for trial_idx in range(trials):
        state = initialize_scene_state(
            ruleset,
            f"sim_{trial_idx}",
            [attacker, defender],
            scene_seed=f"{seed}:{trial_idx}",
        )
        start_att = state.entities[attacker.entity_id].pools.get(vitality_pool_id, 0)
        start_def = state.entities[defender.entity_id].pools.get(vitality_pool_id, 0)
        outcome_decided = False

        for rnd in range(1, max_rounds + 1):
            try:
                res_a = execute_action(
                    ruleset,
                    state,
                    attacker.entity_id,
                    attacker_action_id,
                    target_id=defender.entity_id,
                    bypass_reactions=True,
                )
                state = res_a.state
            except ValueError:
                pass

            if state.entities[defender.entity_id].pools.get(vitality_pool_id, 0) <= 0:
                att_wins += 1
                ttk_rounds.append(rnd)
                outcome_decided = True
                break

            if defender_action_id is not None:
                try:
                    res_d = execute_action(
                        ruleset,
                        state,
                        defender.entity_id,
                        defender_action_id,
                        target_id=attacker.entity_id,
                        bypass_reactions=True,
                    )
                    state = res_d.state
                except ValueError:
                    pass

                if state.entities[attacker.entity_id].pools.get(vitality_pool_id, 0) <= 0:
                    def_wins += 1
                    ttk_rounds.append(rnd)
                    outcome_decided = True
                    break

        if not outcome_decided:
            stalemates += 1
        end_att = state.entities[attacker.entity_id].pools.get(vitality_pool_id, 0)
        end_def = state.entities[defender.entity_id].pools.get(vitality_pool_id, 0)
        att_drains.append(start_att - end_att)
        def_drains.append(start_def - end_def)

    stalemate_rate = round(stalemates / trials, 4)
    avg_def_drain = round(sum(def_drains) / trials, 4)
    warnings: list[str] = []
    if stalemate_rate > 0.5:
        warnings.append(
            f"High stalemate rate ({stalemate_rate * 100:.1f}%) after {max_rounds} rounds."
        )
    if avg_def_drain <= 0.0:
        warnings.append(
            f"Potential mathematical deadlock: action '{attacker_action_id}' dealt "
            f"<= 0 average '{vitality_pool_id}' drain."
        )

    return BalanceSimulationReport(
        trials_run=trials,
        attacker_win_rate=round(att_wins / trials, 4),
        defender_win_rate=round(def_wins / trials, 4),
        stalemate_rate=stalemate_rate,
        avg_ttk_rounds=round(sum(ttk_rounds) / len(ttk_rounds), 3) if ttk_rounds else None,
        min_ttk_rounds=min(ttk_rounds) if ttk_rounds else None,
        max_ttk_rounds=max(ttk_rounds) if ttk_rounds else None,
        avg_attacker_pool_drain=round(sum(att_drains) / trials, 4),
        avg_defender_pool_drain=avg_def_drain,
        deadlock_warnings=tuple(warnings),
        seed=seed,
        ruleset_hash=ruleset.content_hash(),
    )
