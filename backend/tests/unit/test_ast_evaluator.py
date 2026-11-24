"""Unit tests for the sandboxed AST formula parser, evaluator, and explainer."""

from __future__ import annotations

import pytest

from app.ruleset_vm.ast_evaluator import (
    EvalLimits,
    FormulaError,
    evaluate_formula,
    explain_ast_deterministically,
    extract_references,
    parse_formula,
)


@pytest.mark.zero_ai
def test_arithmetic_precedence_comparisons_and_ternary() -> None:
    """AST evaluator respects operator precedence, short-circuit logic, and ternary."""
    assert evaluate_formula("2 + 3 * 4") == 14
    assert evaluate_formula("(2 + 3) * 4 // 3") == 6
    assert evaluate_formula("17 % 5") == 2
    assert evaluate_formula("-5 + +2") == -3

    assert evaluate_formula("false && (@missing.field > 0)", {}) is False
    assert evaluate_formula("true || (@missing.field > 0)", {}) is True
    assert evaluate_formula("3 > 2 ? 10 : 20") == 10
    assert evaluate_formula("false ? 1 : true ? 2 : 3") == 2


@pytest.mark.zero_ai
def test_context_paths_and_whitelisted_functions() -> None:
    """Path references and whitelisted pure functions evaluate accurately."""
    ctx = {
        "@self": {
            "agility": 15,
            "armor_tier": "light",
            "tags": ("martial", "agile"),
            "conditions": ("focused",),
        },
        "@target": {
            "vitality": 12,
        },
    }
    expr = (
        "floor((@self.agility - 10) / 2) + "
        "(@self.armor_tier == 'light' && !has_condition(@self, 'restrained') ? 2 : 0)"
    )
    assert evaluate_formula(expr, ctx) == 4
    assert evaluate_formula("exists(@target.vitality) && !exists(@target.shield)", ctx) is True
    assert evaluate_formula("has_tag(@self, 'agile') && contains('battlefield', 'field')", ctx)
    assert evaluate_formula("clamp(15, 0, 10)") == 10
    assert evaluate_formula("min(9, 4, 7) + max(1, 3) + abs(-5) + ceil(1.2) + round(2.6)") == 17
    assert evaluate_formula("len(@self.tags) + sum(1, 2, 3)", ctx) == 8


@pytest.mark.zero_ai
def test_extract_references_and_deterministic_explanation() -> None:
    """extract_references & explain_ast_deterministically produce traces with 0 AI calls."""
    expr = "floor((@self.brawn - 10) / 2) + (@self.bonus)"
    refs = extract_references(expr)
    assert refs == {"@self.brawn", "@self.bonus"}

    explanation = explain_ast_deterministically(
        expr,
        {"@self": {"brawn": 16, "bonus": 2}},
    )
    assert explanation.value == 5
    assert explanation.referenced_paths == ("@self.bonus", "@self.brawn")
    assert "floor(" in explanation.explanation
    assert "5" in explanation.explanation


@pytest.mark.zero_ai
def test_security_limits_and_error_codes() -> None:
    """AST evaluator rejects syntax errors, disallowed calls, depth > 32, and op > 1000."""
    with pytest.raises(FormulaError) as syn_err:
        parse_formula("1 + * 2")
    assert syn_err.value.code == "RPG-E1001"

    with pytest.raises(FormulaError) as sec_err:
        evaluate_formula("__import__('os')")
    assert sec_err.value.code == "RPG-E1005"

    with pytest.raises(FormulaError) as method_err:
        evaluate_formula("abs(-1).bit_length()")
    assert method_err.value.code == "RPG-E1001"

    with pytest.raises(FormulaError) as zero_err:
        evaluate_formula("10 / 0")
    assert zero_err.value.code == "RPG-E1005"

    deep_expr = "(" * 35 + "1" + ")" * 35
    with pytest.raises(FormulaError) as depth_err:
        parse_formula(deep_expr, max_depth=32)
    assert depth_err.value.code == "RPG-E1002"

    wide_expr = " + ".join(["1"] * 40)
    with pytest.raises(FormulaError) as op_err:
        evaluate_formula(wide_expr, limits=EvalLimits(max_operations=20))
    assert op_err.value.code == "RPG-E1003"
