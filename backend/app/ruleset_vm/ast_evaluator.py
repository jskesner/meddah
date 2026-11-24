"""Safe recursive-descent AST formula parser, sandboxed evaluator, and deterministic explainer."""

from __future__ import annotations

import math
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal, cast

ScalarValue = int | float | bool | str | None
ContextValue = object

DEFAULT_MAX_DEPTH = 32
DEFAULT_MAX_OPERATIONS = 1000
DEFAULT_MAX_WALL_MS = 10.0


class FormulaError(Exception):
    """Structured error raised during formula parsing or sandboxed evaluation."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")


@dataclass(frozen=True)
class EvalLimits:
    """Hard resource bounds enforced on every AST formula evaluation (§8.1)."""

    max_depth: int = DEFAULT_MAX_DEPTH
    max_operations: int = DEFAULT_MAX_OPERATIONS
    max_wall_ms: float = DEFAULT_MAX_WALL_MS


@dataclass(frozen=True)
class FormulaExplanation:
    """Human-readable deterministic trace of a formula and its numeric/boolean result."""

    expression: str
    explanation: str
    value: object
    referenced_paths: tuple[str, ...]


TokenKind = Literal[
    "NUMBER",
    "STRING",
    "IDENT",
    "PATH",
    "OP",
    "LPAREN",
    "RPAREN",
    "COMMA",
    "QUESTION",
    "COLON",
    "EOF",
]


@dataclass(frozen=True)
class _Token:
    kind: TokenKind
    text: str
    pos: int


def _tokenize(expr: str) -> list[_Token]:
    tokens: list[_Token] = []
    idx = 0
    n = len(expr)

    while idx < n:
        ch = expr[idx]
        if ch.isspace():
            idx += 1
            continue

        two = expr[idx : idx + 2]
        if two in {"&&", "||", "==", "!=", "<=", ">=", "//"}:
            tokens.append(_Token("OP", two, idx))
            idx += 2
            continue

        if ch in {"+", "-", "*", "/", "%", "<", ">", "!"}:
            tokens.append(_Token("OP", ch, idx))
            idx += 1
            continue
        if ch == "(":
            tokens.append(_Token("LPAREN", ch, idx))
            idx += 1
            continue
        if ch == ")":
            tokens.append(_Token("RPAREN", ch, idx))
            idx += 1
            continue
        if ch == ",":
            tokens.append(_Token("COMMA", ch, idx))
            idx += 1
            continue
        if ch == "?":
            tokens.append(_Token("QUESTION", ch, idx))
            idx += 1
            continue
        if ch == ":":
            tokens.append(_Token("COLON", ch, idx))
            idx += 1
            continue

        if ch in {"'", '"'}:
            quote = ch
            start = idx
            idx += 1
            buf: list[str] = []
            closed = False
            while idx < n:
                cur = expr[idx]
                if cur == "\\" and idx + 1 < n:
                    nxt = expr[idx + 1]
                    buf.append(nxt)
                    idx += 2
                    continue
                if cur == quote:
                    closed = True
                    idx += 1
                    break
                buf.append(cur)
                idx += 1
            if not closed:
                raise FormulaError("RPG-E1001", f"Unterminated string literal at position {start}")
            tokens.append(_Token("STRING", "".join(buf), start))
            continue

        if ch.isdigit() or (ch == "." and idx + 1 < n and expr[idx + 1].isdigit()):
            start = idx
            seen_dot = ch == "."
            idx += 1
            while idx < n:
                cur = expr[idx]
                if cur.isdigit():
                    idx += 1
                elif cur == "." and not seen_dot:
                    seen_dot = True
                    idx += 1
                else:
                    break
            tokens.append(_Token("NUMBER", expr[start:idx], start))
            continue

        if ch == "@" or ch.isalpha() or ch == "_":
            start = idx
            if ch == "@":
                idx += 1
                if idx >= n or not (expr[idx].isalpha() or expr[idx] == "_"):
                    raise FormulaError(
                        "RPG-E1001", f"Expected scope identifier after '@' at position {start}"
                    )
            while idx < n and (expr[idx].isalnum() or expr[idx] == "_"):
                idx += 1
            while idx < n and expr[idx] == ".":
                idx += 1
                seg_start = idx
                if idx >= n or not (expr[idx].isalpha() or expr[idx] == "_"):
                    raise FormulaError(
                        "RPG-E1001", f"Invalid attribute segment after '.' at position {seg_start}"
                    )
                while idx < n and (expr[idx].isalnum() or expr[idx] == "_"):
                    idx += 1
            word = expr[start:idx]
            if word.startswith("@") or "." in word:
                tokens.append(_Token("PATH", word, start))
            else:
                tokens.append(_Token("IDENT", word, start))
            continue

        raise FormulaError("RPG-E1001", f"Unexpected character {ch!r} at position {idx}")

    tokens.append(_Token("EOF", "", n))
    return tokens


@dataclass(frozen=True)
class LiteralNode:
    """AST node representing a scalar constant."""

    value: ScalarValue


@dataclass(frozen=True)
class PathNode:
    """AST node representing a context lookup path such as @self.vitality."""

    raw_path: str
    segments: tuple[str, ...]


@dataclass(frozen=True)
class UnaryNode:
    """AST node representing a unary prefix operator."""

    op: str
    operand: AstNode


@dataclass(frozen=True)
class BinaryNode:
    """AST node representing a binary arithmetic, comparison, or boolean operator."""

    op: str
    left: AstNode
    right: AstNode


@dataclass(frozen=True)
class TernaryNode:
    """AST node representing conditional expression `cond ? if_true : if_false`."""

    condition: AstNode
    true_branch: AstNode
    false_branch: AstNode


@dataclass(frozen=True)
class CallNode:
    """AST node representing a whitelisted pure function call."""

    func_name: str
    args: tuple[AstNode, ...]


AstNode = LiteralNode | PathNode | UnaryNode | BinaryNode | TernaryNode | CallNode


class _Parser:
    def __init__(self, tokens: list[_Token], max_depth: int) -> None:
        self._tokens = tokens
        self._idx = 0
        self._depth = 0
        self._max_depth = max_depth

    def _cur(self) -> _Token:
        return self._tokens[self._idx]

    def _consume(self) -> _Token:
        tok = self._tokens[self._idx]
        self._idx += 1
        return tok

    def _enter_depth(self) -> None:
        self._depth += 1
        if self._depth > self._max_depth:
            raise FormulaError(
                "RPG-E1002",
                f"Formula AST exceeded maximum nesting depth of {self._max_depth}",
            )

    def _exit_depth(self) -> None:
        self._depth -= 1

    def parse(self) -> AstNode:
        node = self._parse_ternary()
        if self._cur().kind != "EOF":
            tok = self._cur()
            raise FormulaError("RPG-E1001", f"Unexpected token {tok.text!r} at position {tok.pos}")
        return node

    def _parse_ternary(self) -> AstNode:
        self._enter_depth()
        try:
            cond = self._parse_or()
            if self._cur().kind == "QUESTION":
                self._consume()
                true_branch = self._parse_ternary()
                if self._cur().kind != "COLON":
                    raise FormulaError(
                        "RPG-E1001",
                        f"Expected ':' in ternary expression at position {self._cur().pos}",
                    )
                self._consume()
                false_branch = self._parse_ternary()
                return TernaryNode(cond, true_branch, false_branch)
            return cond
        finally:
            self._exit_depth()

    def _parse_or(self) -> AstNode:
        node = self._parse_and()
        while (self._cur().kind == "OP" and self._cur().text == "||") or (
            self._cur().kind == "IDENT" and self._cur().text == "or"
        ):
            self._consume()
            right = self._parse_and()
            node = BinaryNode("||", node, right)
        return node

    def _parse_and(self) -> AstNode:
        node = self._parse_equality()
        while (self._cur().kind == "OP" and self._cur().text == "&&") or (
            self._cur().kind == "IDENT" and self._cur().text == "and"
        ):
            self._consume()
            right = self._parse_equality()
            node = BinaryNode("&&", node, right)
        return node

    def _parse_equality(self) -> AstNode:
        node = self._parse_comparison()
        while self._cur().kind == "OP" and self._cur().text in {"==", "!="}:
            op = self._consume().text
            right = self._parse_comparison()
            node = BinaryNode(op, node, right)
        return node

    def _parse_comparison(self) -> AstNode:
        node = self._parse_additive()
        while self._cur().kind == "OP" and self._cur().text in {"<", "<=", ">", ">="}:
            op = self._consume().text
            right = self._parse_additive()
            node = BinaryNode(op, node, right)
        return node

    def _parse_additive(self) -> AstNode:
        node = self._parse_multiplicative()
        while self._cur().kind == "OP" and self._cur().text in {"+", "-"}:
            op = self._consume().text
            right = self._parse_multiplicative()
            node = BinaryNode(op, node, right)
        return node

    def _parse_multiplicative(self) -> AstNode:
        node = self._parse_unary()
        while self._cur().kind == "OP" and self._cur().text in {"*", "/", "//", "%"}:
            op = self._consume().text
            right = self._parse_unary()
            node = BinaryNode(op, node, right)
        return node

    def _parse_unary(self) -> AstNode:
        self._enter_depth()
        try:
            tok = self._cur()
            if (tok.kind == "OP" and tok.text in {"+", "-", "!"}) or (
                tok.kind == "IDENT" and tok.text == "not"
            ):
                self._consume()
                op = "!" if tok.text in {"!", "not"} else tok.text
                return UnaryNode(op, self._parse_unary())
            return self._parse_primary()
        finally:
            self._exit_depth()

    def _parse_primary(self) -> AstNode:
        tok = self._cur()
        if tok.kind == "NUMBER":
            self._consume()
            num_val: int | float = float(tok.text) if "." in tok.text else int(tok.text)
            return LiteralNode(num_val)
        if tok.kind == "STRING":
            self._consume()
            return LiteralNode(tok.text)
        if tok.kind == "PATH":
            self._consume()
            return PathNode(tok.text, tuple(tok.text.split(".")))
        if tok.kind == "LPAREN":
            self._consume()
            inner = self._parse_ternary()
            if self._cur().kind != "RPAREN":
                raise FormulaError("RPG-E1001", f"Expected ')' at position {self._cur().pos}")
            self._consume()
            return inner
        if tok.kind == "IDENT":
            self._consume()
            if self._cur().kind == "LPAREN":
                self._consume()
                args: list[AstNode] = []
                if self._cur().kind != "RPAREN":
                    while True:
                        args.append(self._parse_ternary())
                        if self._cur().kind == "COMMA":
                            self._consume()
                            continue
                        break
                if self._cur().kind != "RPAREN":
                    raise FormulaError(
                        "RPG-E1001",
                        f"Expected ')' after arguments at position {self._cur().pos}",
                    )
                self._consume()
                return CallNode(tok.text, tuple(args))
            lowered = tok.text.lower()
            if lowered == "true":
                return LiteralNode(True)
            if lowered == "false":
                return LiteralNode(False)
            if lowered in {"none", "null"}:
                return LiteralNode(None)
            return PathNode(tok.text, (tok.text,))

        raise FormulaError(
            "RPG-E1001", f"Expected expression near {tok.text!r} at position {tok.pos}"
        )


def parse_formula(expr: str, max_depth: int = DEFAULT_MAX_DEPTH) -> AstNode:
    """Parse an expression string into an AST while enforcing max AST depth."""
    if not expr or not expr.strip():
        raise FormulaError("RPG-E1001", "Formula expression must not be empty.")
    tokens = _tokenize(expr)
    return _Parser(tokens, max_depth=max_depth).parse()


def extract_references(expr: str) -> set[str]:
    """Return all variable/context paths referenced by an AST expression."""
    ast_root = parse_formula(expr)
    refs: set[str] = set()

    def _walk(node: AstNode) -> None:
        if isinstance(node, PathNode):
            refs.add(node.raw_path)
        elif isinstance(node, UnaryNode):
            _walk(node.operand)
        elif isinstance(node, BinaryNode):
            _walk(node.left)
            _walk(node.right)
        elif isinstance(node, TernaryNode):
            _walk(node.condition)
            _walk(node.true_branch)
            _walk(node.false_branch)
        elif isinstance(node, CallNode):
            for arg in node.args:
                _walk(arg)

    _walk(ast_root)
    return refs


def _as_number(val: object, context: str) -> int | float:
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        raise FormulaError("RPG-E1005", f"Expected numeric value for {context}, got {val!r}")
    return val


def _extract_collection(container: object, field_name: str) -> object:
    if isinstance(container, Mapping):
        mapping = cast(Mapping[object, object], container)
        return mapping.get(field_name, ())
    return container


def _fn_floor(args: Sequence[object]) -> int:
    _require_arity("floor", args, 1)
    return math.floor(_as_number(args[0], "floor()"))


def _fn_ceil(args: Sequence[object]) -> int:
    _require_arity("ceil", args, 1)
    return math.ceil(_as_number(args[0], "ceil()"))


def _fn_round(args: Sequence[object]) -> int | float:
    if len(args) == 1:
        return round(_as_number(args[0], "round()"))
    if len(args) == 2:
        digits = _as_number(args[1], "round() digits")
        if not isinstance(digits, int):
            raise FormulaError("RPG-E1005", "round() second argument must be an integer")
        return round(_as_number(args[0], "round()"), digits)
    raise FormulaError("RPG-E1005", f"round() expects 1 or 2 arguments, got {len(args)}")


def _fn_abs(args: Sequence[object]) -> int | float:
    _require_arity("abs", args, 1)
    return abs(_as_number(args[0], "abs()"))


def _fn_min(args: Sequence[object]) -> int | float:
    if not args:
        raise FormulaError("RPG-E1005", "min() requires at least 1 argument")
    nums = [_as_number(a, "min()") for a in args]
    return min(nums)


def _fn_max(args: Sequence[object]) -> int | float:
    if not args:
        raise FormulaError("RPG-E1005", "max() requires at least 1 argument")
    nums = [_as_number(a, "max()") for a in args]
    return max(nums)


def _fn_clamp(args: Sequence[object]) -> int | float:
    _require_arity("clamp", args, 3)
    val = _as_number(args[0], "clamp() value")
    low = _as_number(args[1], "clamp() low")
    high = _as_number(args[2], "clamp() high")
    if low > high:
        raise FormulaError("RPG-E1005", f"clamp() low ({low}) exceeds high ({high})")
    if val < low:
        return low
    if val > high:
        return high
    return val


def _fn_len(args: Sequence[object]) -> int:
    _require_arity("len", args, 1)
    val = args[0]
    if isinstance(val, str):
        return len(val)
    if isinstance(val, Sequence):
        return len(cast(Sequence[object], val))
    if isinstance(val, Mapping):
        return len(cast(Mapping[object, object], val))
    if isinstance(val, set):
        return len(cast(set[object], val))
    if isinstance(val, frozenset):
        return len(cast(frozenset[object], val))
    raise FormulaError("RPG-E1005", f"len() unsupported for {val!r}")


def _fn_sum(args: Sequence[object]) -> int | float:
    if len(args) == 1 and isinstance(args[0], (list, tuple)):
        items = cast(Sequence[object], args[0])
        return sum(_as_number(item, "sum()") for item in items)
    return sum(_as_number(item, "sum()") for item in args)


def _fn_contains(args: Sequence[object]) -> bool:
    _require_arity("contains", args, 2)
    container, needle = args[0], args[1]
    if isinstance(container, str):
        return isinstance(needle, str) and needle in container
    if isinstance(container, Sequence):
        return needle in cast(Sequence[object], container)
    if isinstance(container, Mapping):
        return needle in cast(Mapping[object, object], container)
    if isinstance(container, set):
        return needle in cast(set[object], container)
    if isinstance(container, frozenset):
        return needle in cast(frozenset[object], container)
    return False


def _fn_has_tag(args: Sequence[object]) -> bool:
    _require_arity("has_tag", args, 2)
    tags_obj = _extract_collection(args[0], "tags")
    tag_name = args[1]
    if not isinstance(tag_name, str):
        return False
    if isinstance(tags_obj, str):
        return False
    if isinstance(tags_obj, Sequence):
        return tag_name in cast(Sequence[object], tags_obj)
    if isinstance(tags_obj, Mapping):
        return tag_name in cast(Mapping[object, object], tags_obj)
    if isinstance(tags_obj, set):
        return tag_name in cast(set[object], tags_obj)
    if isinstance(tags_obj, frozenset):
        return tag_name in cast(frozenset[object], tags_obj)
    return False


def _fn_has_condition(args: Sequence[object]) -> bool:
    _require_arity("has_condition", args, 2)
    conds_obj = _extract_collection(args[0], "conditions")
    cond_name = args[1]
    if not isinstance(cond_name, str):
        return False
    if isinstance(conds_obj, str):
        return False
    if isinstance(conds_obj, Mapping):
        return cond_name in cast(Mapping[object, object], conds_obj)
    if isinstance(conds_obj, Sequence):
        return cond_name in cast(Sequence[object], conds_obj)
    if isinstance(conds_obj, set):
        return cond_name in cast(set[object], conds_obj)
    if isinstance(conds_obj, frozenset):
        return cond_name in cast(frozenset[object], conds_obj)
    return False


def _require_arity(fn_name: str, args: Sequence[object], expected: int) -> None:
    if len(args) != expected:
        raise FormulaError(
            "RPG-E1005", f"{fn_name}() expects {expected} arguments, got {len(args)}"
        )


WHITELISTED_FUNCTIONS: dict[str, Callable[[Sequence[object]], object]] = {
    "abs": _fn_abs,
    "ceil": _fn_ceil,
    "clamp": _fn_clamp,
    "contains": _fn_contains,
    "floor": _fn_floor,
    "has_condition": _fn_has_condition,
    "has_tag": _fn_has_tag,
    "len": _fn_len,
    "max": _fn_max,
    "min": _fn_min,
    "round": _fn_round,
    "sum": _fn_sum,
}


class _Evaluator:
    def __init__(self, context: Mapping[str, object], limits: EvalLimits) -> None:
        self._context = context
        self._limits = limits
        self._ops = 0
        self._start = time.perf_counter()

    def _tick(self) -> None:
        self._ops += 1
        if self._ops > self._limits.max_operations:
            raise FormulaError(
                "RPG-E1003",
                f"Formula exceeded maximum operation budget ({self._limits.max_operations})",
            )
        elapsed_ms = (time.perf_counter() - self._start) * 1000.0
        if elapsed_ms > self._limits.max_wall_ms:
            raise FormulaError(
                "RPG-E1004",
                f"Formula exceeded wall-clock limit ({self._limits.max_wall_ms}ms)",
            )

    def _resolve_path(self, segments: tuple[str, ...]) -> object:
        cur: object = self._context
        for seg in segments:
            if isinstance(cur, Mapping):
                cur_map = cast(Mapping[object, object], cur)
                if seg not in cur_map:
                    raise FormulaError(
                        "RPG-E1005", f"Unknown context reference '{'.'.join(segments)}'"
                    )
                cur = cur_map[seg]
            else:
                raise FormulaError(
                    "RPG-E1005",
                    f"Cannot traverse '{seg}' inside non-mapping reference '{'.'.join(segments)}'",
                )
        return cur

    def eval_node(self, node: AstNode) -> object:
        self._tick()
        if isinstance(node, LiteralNode):
            return node.value
        if isinstance(node, PathNode):
            return self._resolve_path(node.segments)
        if isinstance(node, UnaryNode):
            operand = self.eval_node(node.operand)
            if node.op == "!":
                return not bool(operand)
            num = _as_number(operand, f"unary '{node.op}'")
            return -num if node.op == "-" else num
        if isinstance(node, TernaryNode):
            cond = self.eval_node(node.condition)
            return self.eval_node(node.true_branch if bool(cond) else node.false_branch)
        if isinstance(node, BinaryNode):
            return self._eval_binary(node)
        return self._eval_call(node)

    def _eval_binary(self, node: BinaryNode) -> object:
        if node.op == "&&":
            left_val = self.eval_node(node.left)
            return False if not bool(left_val) else bool(self.eval_node(node.right))
        if node.op == "||":
            left_val = self.eval_node(node.left)
            return True if bool(left_val) else bool(self.eval_node(node.right))

        left_val = self.eval_node(node.left)
        right_val = self.eval_node(node.right)

        if node.op == "==":
            return left_val == right_val
        if node.op == "!=":
            return left_val != right_val
        if node.op in {"<", "<=", ">", ">="}:
            l_num = _as_number(left_val, f"left side of '{node.op}'")
            r_num = _as_number(right_val, f"right side of '{node.op}'")
            if node.op == "<":
                return l_num < r_num
            if node.op == "<=":
                return l_num <= r_num
            if node.op == ">":
                return l_num > r_num
            return l_num >= r_num

        if node.op == "+" and isinstance(left_val, str) and isinstance(right_val, str):
            return left_val + right_val

        l_num = _as_number(left_val, f"left side of '{node.op}'")
        r_num = _as_number(right_val, f"right side of '{node.op}'")
        if node.op == "+":
            return l_num + r_num
        if node.op == "-":
            return l_num - r_num
        if node.op == "*":
            return l_num * r_num
        if node.op in {"/", "//", "%"}:
            if r_num == 0:
                raise FormulaError("RPG-E1005", "Division or modulo by zero in formula")
            if node.op == "/":
                return l_num / r_num
            if node.op == "//":
                return l_num // r_num
            return l_num % r_num
        raise FormulaError("RPG-E1001", f"Unsupported operator '{node.op}'")

    def _eval_call(self, node: CallNode) -> object:
        if node.func_name == "exists":
            _require_arity("exists", node.args, 1)
            target_node = node.args[0]
            try:
                resolved = self.eval_node(target_node)
            except FormulaError as exc:
                if exc.code == "RPG-E1005":
                    return False
                raise
            return resolved is not None

        fn = WHITELISTED_FUNCTIONS.get(node.func_name)
        if fn is None:
            raise FormulaError(
                "RPG-E1005", f"Function '{node.func_name}' is not allowed in formulas"
            )
        evaluated_args = [self.eval_node(arg) for arg in node.args]
        return fn(evaluated_args)


def evaluate_formula(
    expr: str,
    context: Mapping[str, object] | None = None,
    limits: EvalLimits | None = None,
) -> object:
    """Safely parse and evaluate an AST formula against a read-only context mapping."""
    active_limits = limits or EvalLimits()
    ast_root = parse_formula(expr, max_depth=active_limits.max_depth)
    evaluator = _Evaluator(context or {}, active_limits)
    return evaluator.eval_node(ast_root)


def _describe_node(node: AstNode) -> str:
    if isinstance(node, LiteralNode):
        return repr(node.value)
    if isinstance(node, PathNode):
        return node.raw_path
    if isinstance(node, UnaryNode):
        return (
            f"not ({_describe_node(node.operand)})"
            if node.op == "!"
            else f"{node.op}({_describe_node(node.operand)})"
        )
    if isinstance(node, BinaryNode):
        op_words = {
            "&&": "AND",
            "||": "OR",
            "==": "equals",
            "!=": "does not equal",
            ">=": "is at least",
            "<=": "is at most",
            ">": "is greater than",
            "<": "is less than",
        }
        label = op_words.get(node.op, node.op)
        return f"({_describe_node(node.left)} {label} {_describe_node(node.right)})"
    if isinstance(node, TernaryNode):
        return (
            f"if ({_describe_node(node.condition)}) then ({_describe_node(node.true_branch)}) "
            f"else ({_describe_node(node.false_branch)})"
        )
    args_desc = ", ".join(_describe_node(arg) for arg in node.args)
    return f"{node.func_name}({args_desc})"


def explain_ast_deterministically(
    expr: str,
    context: Mapping[str, object] | None = None,
    limits: EvalLimits | None = None,
) -> FormulaExplanation:
    """Generate a deterministic plain-English trace and evaluated result (0 LLM calls)."""
    active_limits = limits or EvalLimits()
    ast_root = parse_formula(expr, max_depth=active_limits.max_depth)
    refs = tuple(sorted(extract_references(expr)))
    ctx = context or {}
    result = _Evaluator(ctx, active_limits).eval_node(ast_root)
    prose = f"{_describe_node(ast_root)} -> {result!r}"
    return FormulaExplanation(
        expression=expr,
        explanation=prose,
        value=result,
        referenced_paths=refs,
    )
