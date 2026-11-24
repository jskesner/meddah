"""Deterministic randomizer resolution across all 6 Ruleset VM paradigms."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field

from app.ruleset_vm.ast_evaluator import FormulaError, evaluate_formula
from app.ruleset_vm.blocks import DeckSpec, OutcomeTier, RandomizerKind, RandomizerSpec
from app.ruleset_vm.rng import DeterministicRngStream

_MAX_DICE_PER_TERM = 100
_MAX_EXPLOSIONS_PER_DIE = 50
_DICE_TERM_RE = re.compile(
    r"^(?P<count>\d+)d(?P<sides>\d+)(?:(?P<keep_mode>kh|kl)(?P<keep>\d+))?(?P<explode>!)?$",
    re.IGNORECASE,
)


class DeckRuntimeState(BaseModel):
    """Immutable per-scene runtime piles for a named DeckSpec."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    draw_pile: tuple[str, ...]
    discard_pile: tuple[str, ...] = ()


class RollResult(BaseModel):
    """Audit-complete result of resolving a RandomizerSpec and OutcomeTiers."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: RandomizerKind
    stream_name: str
    position_before: int = Field(ge=0)
    position_after: int = Field(ge=0)
    raw_rolls: tuple[int, ...] = ()
    kept_rolls: tuple[int, ...] = ()
    modifier: int | float = 0
    total: int | float = 0
    hits: int | None = None
    is_glitch: bool = False
    symbols: tuple[str, ...] = ()
    drawn_cards: tuple[str, ...] = ()
    target: int | float | None = None
    tier_id: str | None = None
    tier_label: str | None = None
    breakdown: str = ""


def _coerce_number(val: object, label: str) -> int | float:
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        raise FormulaError("RPG-E1005", f"Expected numeric result for {label}, got {val!r}")
    return val


def _roll_single_die(
    rng: DeterministicRngStream,
    sides: int,
    explode: bool,
) -> tuple[int, tuple[int, ...]]:
    """Roll one die with bounded explosion retries, returning (total, raw_sequence)."""
    first = rng.randint(1, sides)
    sequence = [first]
    running = first
    explosions = 0
    cur = first
    while explode and sides > 1 and cur == sides and explosions < _MAX_EXPLOSIONS_PER_DIE:
        cur = rng.randint(1, sides)
        sequence.append(cur)
        running += cur
        explosions += 1
    return running, tuple(sequence)


def _evaluate_dice_formula(
    formula: str,
    rng: DeterministicRngStream,
    eval_ctx: Mapping[str, object],
) -> tuple[tuple[int, ...], tuple[int, ...], int | float, str]:
    """Evaluate dice expressions with NdS[kh/klK][!] terms, +/- signs, constants, and paths."""
    cleaned = formula.strip()
    if not cleaned:
        return (), (), 0, "0"

    # Split top-level '+' and '-' terms cleanly while preserving signs
    parts: list[tuple[int, str]] = []
    cur: list[str] = []
    sign = 1
    idx = 0
    depth = 0
    while idx < len(cleaned):
        ch = cleaned[idx]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        if depth == 0 and ch in {"+", "-"}:
            token = "".join(cur).strip()
            if token:
                parts.append((sign, token))
                cur = []
            sign = 1 if ch == "+" else -1
            idx += 1
            continue
        cur.append(ch)
        idx += 1
    tail = "".join(cur).strip()
    if tail:
        parts.append((sign, tail))

    raw_rolls: list[int] = []
    kept_rolls: list[int] = []
    running_total: int | float = 0
    desc_parts: list[str] = []

    for term_sign, term_str in parts:
        dice_match = _DICE_TERM_RE.match(term_str)
        if dice_match is not None:
            count = int(dice_match.group("count"))
            sides = int(dice_match.group("sides"))
            keep_mode = dice_match.group("keep_mode")
            keep_raw = dice_match.group("keep")
            explode = dice_match.group("explode") is not None
            if count < 1 or count > _MAX_DICE_PER_TERM:
                raise FormulaError(
                    "RPG-E1006", f"Dice count {count} out of range [1, {_MAX_DICE_PER_TERM}]"
                )
            if sides < 1 or sides > 1000:
                raise FormulaError("RPG-E1006", f"Die sides {sides} out of range [1, 1000]")

            die_totals: list[int] = []
            for _ in range(count):
                die_val, die_raw = _roll_single_die(rng, sides, explode)
                raw_rolls.extend(die_raw)
                die_totals.append(die_val)

            if keep_mode and keep_raw:
                keep_count = max(1, min(int(keep_raw), count))
                ordered = sorted(die_totals, reverse=(keep_mode.lower() == "kh"))
                term_kept = ordered[:keep_count]
            else:
                term_kept = list(die_totals)

            kept_rolls.extend(term_kept)
            term_val: int | float = sum(term_kept)
            prefix = "-" if term_sign < 0 else ("+" if desc_parts else "")
            desc_parts.append(f"{prefix}{term_str}[{','.join(str(v) for v in term_kept)}]")
        else:
            term_val = _coerce_number(
                evaluate_formula(term_str, eval_ctx), f"dice term {term_str!r}"
            )
            prefix = "-" if term_sign < 0 else ("+" if desc_parts else "")
            desc_parts.append(f"{prefix}{term_val}")
        running_total += term_sign * term_val

    return tuple(raw_rolls), tuple(kept_rolls), running_total, " ".join(desc_parts)


def _resolve_dice_pool(
    spec: RandomizerSpec,
    rng: DeterministicRngStream,
    eval_ctx: Mapping[str, object],
    modifier_value: int | float,
) -> tuple[tuple[int, ...], tuple[int, ...], int, bool, tuple[str, ...], str]:
    pool_count_val = _coerce_number(
        evaluate_formula(spec.pool_size_formula, eval_ctx), "pool_size_formula"
    )
    pool_count = max(0, min(int(pool_count_val) + int(modifier_value), _MAX_DICE_PER_TERM))
    rolls = [rng.randint(1, spec.die_sides) for _ in range(pool_count)]
    hits = sum(1 for r in rolls if r >= spec.success_threshold)
    glitch_count = sum(1 for r in rolls if r == spec.glitch_face)
    is_glitch = bool(rolls) and (glitch_count / len(rolls)) > spec.glitch_ratio
    symbols: list[str] = []
    if spec.face_symbols:
        for r in rolls:
            symbols.extend(spec.face_symbols.get(r, ()))
    desc = f"{pool_count}d{spec.die_sides}{rolls} -> {hits} hits"
    if is_glitch:
        desc += " (GLITCH)"
    return tuple(rolls), tuple(rolls), hits, is_glitch, tuple(symbols), desc


def _resolve_step_dice(
    spec: RandomizerSpec,
    rng: DeterministicRngStream,
    eval_ctx: Mapping[str, object],
    modifier_value: int | float,
) -> tuple[tuple[int, ...], tuple[int, ...], int | float, tuple[str, ...], str]:
    sides = spec.die_sides
    if spec.step_die_formula:
        raw_step = spec.step_die_formula.strip()
        if raw_step.lower().startswith("d") and raw_step[1:].isdigit():
            sides = int(raw_step[1:])
        else:
            step_val = evaluate_formula(raw_step, eval_ctx)
            if (
                isinstance(step_val, str)
                and step_val.lower().startswith("d")
                and step_val[1:].isdigit()
            ):
                sides = int(step_val[1:])
            else:
                sides = int(_coerce_number(step_val, "step_die_formula"))
    sides = max(2, min(sides, 1000))

    trait_total, trait_seq = _roll_single_die(rng, sides, spec.explode)
    raw_all = list(trait_seq)
    chosen = trait_total

    symbols: list[str] = []
    for face in trait_seq:
        symbols.extend(spec.face_symbols.get(face, ()))

    desc = f"d{sides}[{','.join(str(x) for x in trait_seq)}]"
    if spec.wild_die_sides is not None:
        wild_total, wild_seq = _roll_single_die(rng, spec.wild_die_sides, spec.explode)
        raw_all.extend(wild_seq)
        chosen = max(trait_total, wild_total)
        desc += f" / wild d{spec.wild_die_sides}[{','.join(str(x) for x in wild_seq)}]"
    total = chosen + modifier_value
    if modifier_value:
        desc += f" + {modifier_value}"
    return tuple(raw_all), (chosen,), total, tuple(symbols), f"{desc} = {total}"


def _draw_from_deck(
    spec: RandomizerSpec,
    deck_spec: DeckSpec,
    deck_states: Mapping[str, DeckRuntimeState],
    rng: DeterministicRngStream,
    modifier_value: int | float,
) -> tuple[tuple[str, ...], DeckRuntimeState, int | float, str]:
    deck_id = deck_spec.deck_id
    state = deck_states.get(deck_id)
    if state is None:
        shuffled = tuple(rng.shuffle(deck_spec.cards))
        state = DeckRuntimeState(draw_pile=shuffled, discard_pile=())

    draw_pile = list(state.draw_pile)
    discard_pile = list(state.discard_pile)
    drawn: list[str] = []

    for _ in range(spec.draw_count):
        if not draw_pile:
            if not spec.reshuffle_on_empty or not discard_pile:
                break
            draw_pile = rng.shuffle(discard_pile)
            discard_pile = []
        card = draw_pile.pop(0)
        drawn.append(card)
        discard_pile.append(card)

    card_sum = sum(deck_spec.card_values.get(card, 0) for card in drawn)
    total = card_sum + modifier_value
    next_state = DeckRuntimeState(draw_pile=tuple(draw_pile), discard_pile=tuple(discard_pile))
    desc = f"drew {drawn} (value={card_sum}, mod={modifier_value}) = {total}"
    return tuple(drawn), next_state, total, desc


def _match_outcome_tier(
    tiers: Sequence[OutcomeTier],
    roll_ctx: Mapping[str, object],
    eval_ctx: Mapping[str, object],
) -> OutcomeTier | None:
    merged_ctx: dict[str, object] = dict(eval_ctx)
    merged_ctx["@roll"] = roll_ctx
    for tier in tiers:
        if bool(evaluate_formula(tier.condition, merged_ctx)):
            return tier
    return None


def resolve_randomizer(
    spec: RandomizerSpec,
    rng: DeterministicRngStream,
    eval_ctx: Mapping[str, object],
    *,
    deck_specs: Mapping[str, DeckSpec] | None = None,
    deck_states: Mapping[str, DeckRuntimeState] | None = None,
    modifier_value: int | float = 0,
    target_value: int | float | None = None,
    tiers: Sequence[OutcomeTier] = (),
    wager_bonus: int | float = 0,
) -> tuple[RollResult, dict[str, DeckRuntimeState]]:
    """Resolve any of the 6 Ruleset VM randomizer types and match OutcomeTiers."""
    pos_before = rng.position
    next_decks: dict[str, DeckRuntimeState] = dict(deck_states or {})

    raw_rolls: tuple[int, ...] = ()
    kept_rolls: tuple[int, ...] = ()
    hits: int | None = None
    is_glitch = False
    symbols: tuple[str, ...] = ()
    drawn_cards: tuple[str, ...] = ()
    total: int | float = 0
    breakdown = ""

    if spec.kind == "dice_formula":
        raw_rolls, kept_rolls, base_total, dice_desc = _evaluate_dice_formula(
            spec.formula or "0", rng, eval_ctx
        )
        total = base_total + modifier_value
        breakdown = (
            f"{dice_desc} + mod({modifier_value}) = {total}"
            if modifier_value
            else f"{dice_desc} = {total}"
        )
    elif spec.kind == "dice_pool":
        raw_rolls, kept_rolls, hits, is_glitch, symbols, breakdown = _resolve_dice_pool(
            spec, rng, eval_ctx, modifier_value
        )
        total = hits
    elif spec.kind == "step_dice":
        raw_rolls, kept_rolls, total, symbols, breakdown = _resolve_step_dice(
            spec, rng, eval_ctx, modifier_value
        )
    elif spec.kind == "card_deck":
        if spec.deck_id is None or not deck_specs or spec.deck_id not in deck_specs:
            raise FormulaError("RPG-E2002", f"Missing card deck definition for '{spec.deck_id}'")
        drawn_cards, updated_deck, total, breakdown = _draw_from_deck(
            spec, deck_specs[spec.deck_id], next_decks, rng, modifier_value
        )
        next_decks[spec.deck_id] = updated_deck
    elif spec.kind == "resource_wager":
        total = spec.base_value + modifier_value + wager_bonus
        breakdown = (
            f"wager({wager_bonus}) + base({spec.base_value}) + mod({modifier_value}) = {total}"
        )
    else:
        total = spec.base_value + modifier_value
        breakdown = f"narrative({total})"

    raw_min = min(raw_rolls) if raw_rolls else 0
    raw_max = max(raw_rolls) if raw_rolls else 0
    roll_ctx: dict[str, object] = {
        "total": total,
        "modifier": modifier_value,
        "target": target_value if target_value is not None else 0,
        "hits": hits if hits is not None else 0,
        "is_glitch": is_glitch,
        "raw_min": raw_min,
        "raw_max": raw_max,
        "symbols": symbols,
        "drawn_cards": drawn_cards,
    }
    matched_tier = _match_outcome_tier(tiers, roll_ctx, eval_ctx)
    pos_after = rng.position

    result = RollResult(
        kind=spec.kind,
        stream_name=rng.stream_name,
        position_before=pos_before,
        position_after=pos_after,
        raw_rolls=raw_rolls,
        kept_rolls=kept_rolls,
        modifier=modifier_value,
        total=total,
        hits=hits,
        is_glitch=is_glitch,
        symbols=symbols,
        drawn_cards=drawn_cards,
        target=target_value,
        tier_id=matched_tier.tier_id if matched_tier else None,
        tier_label=matched_tier.label if matched_tier else None,
        breakdown=breakdown,
    )
    return result, next_decks
