"""CI linter enforcing Zero-Assumption Agnosticism (Golden Rule #1) and VM determinism."""

from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path

FORBIDDEN_UNIGRAMS: frozenset[str] = frozenset(
    {
        "hp",
        "ac",
        "d20",
        "mana",
        "strength",
        "dexterity",
        "constitution",
        "intelligence",
        "wisdom",
        "charisma",
    }
)

FORBIDDEN_BIGRAMS: frozenset[str] = frozenset(
    {
        "hit_points",
        "armor_class",
        "saving_throw",
        "spell_slot",
        "character_class",
        "character_race",
        "character_level",
    }
)

FORBIDDEN_BUILTINS: frozenset[str] = frozenset({"eval", "exec", "compile", "__import__"})
TARGET_SUBDIRS: tuple[str, ...] = (
    "ruleset_vm",
    "mud_parser",
    "storage",
    "world_gen",
    "systems",
    "ingestion",
    "agents",
    "vtt",
)


@dataclass(frozen=True)
class LintIssue:
    """Represents a single agnosticism or determinism violation."""

    path: Path
    line: int
    rule: str
    detail: str

    def format(self) -> str:
        """Render diagnostic in compiler-style file:line format."""
        return f"{self.path}:{self.line}: [{self.rule}] {self.detail}"


def split_tokens(identifier: str) -> list[str]:
    """Split snake_case and camelCase identifiers into lowercase tokens."""
    camel_split = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", identifier)
    camel_split = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", camel_split)
    return [tok.lower() for tok in re.split(r"[^A-Za-z0-9]+", camel_split) if tok]


def find_forbidden_term(text: str) -> str | None:
    """Return the first forbidden game-specific term found in token sequence, if any."""
    tokens = split_tokens(text)
    for tok in tokens:
        if tok in FORBIDDEN_UNIGRAMS:
            return tok
    for idx in range(len(tokens) - 1):
        bigram = f"{tokens[idx]}_{tokens[idx + 1]}"
        if bigram in FORBIDDEN_BIGRAMS:
            return bigram
    return None


def _is_docstring_node(parent: ast.AST | None, node: ast.AST) -> bool:
    """Return True if node is the leading docstring expression of a module, class, or function."""
    if not isinstance(parent, ast.Expr) or parent.value is not node:
        return False
    return isinstance(
        getattr(parent, "_scope_parent", None),
        (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef),
    )


def _annotate_parents(tree: ast.AST) -> dict[int, ast.AST]:
    """Build child id -> parent AST node map and mark docstring expressions."""
    parents: dict[int, ast.AST] = {}
    for parent in ast.walk(tree):
        body = getattr(parent, "body", None)
        if isinstance(body, list) and body:
            first = body[0]
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                first._scope_parent = parent  # type: ignore[attr-defined]
        for child in ast.iter_child_nodes(parent):
            parents[id(child)] = parent
    return parents


def _line_has_marker(lines: list[str], lineno: int, marker: str) -> bool:
    """Check whether source line carries an explicit allow comment."""
    if 1 <= lineno <= len(lines):
        return marker in lines[lineno - 1]
    return False


class _AgnosticismVisitor(ast.NodeVisitor):
    """AST visitor detecting hardcoded game terms and non-deterministic primitives."""

    def __init__(self, path: Path, lines: list[str], parents: dict[int, ast.AST]) -> None:
        self.path = path
        self.lines = lines
        self.parents = parents
        self.issues: list[LintIssue] = []

    def _record_term(self, text: str, lineno: int, context: str) -> None:
        if _line_has_marker(self.lines, lineno, "agnosticism-allow"):
            return
        match = find_forbidden_term(text)
        if match is not None:
            self.issues.append(
                LintIssue(
                    path=self.path,
                    line=lineno,
                    rule="AGN-001",
                    detail=f"Forbidden game-specific term '{match}' in {context} ({text!r})",
                )
            )

    def _record_det(self, lineno: int, rule: str, detail: str) -> None:
        if _line_has_marker(self.lines, lineno, "determinism-allow"):
            return
        self.issues.append(LintIssue(path=self.path, line=lineno, rule=rule, detail=detail))

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._record_term(node.name, node.lineno, "function name")
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._record_term(node.name, node.lineno, "async function name")
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._record_term(node.name, node.lineno, "class name")
        self.generic_visit(node)

    def visit_arg(self, node: ast.arg) -> None:
        self._record_term(node.arg, node.lineno, "argument name")
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Store):
            self._record_term(node.id, node.lineno, "variable name")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        self._record_term(node.attr, node.lineno, "attribute name")
        if isinstance(node.value, ast.Name) and (
            (node.value.id == "time" and node.attr == "time")
            or (node.value.id == "datetime" and node.attr in {"now", "utcnow"})
        ):
            self._record_det(
                node.lineno,
                "DET-002",
                f"Forbidden wall-clock call '{node.value.id}.{node.attr}()' in engine logic",
            )
        self.generic_visit(node)

    def visit_Dict(self, node: ast.Dict) -> None:
        for key in node.keys:
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                self._record_term(key.value, key.lineno, "dictionary key")
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        parent = self.parents.get(id(node))
        if isinstance(node.value, str) and not _is_docstring_node(parent, node):
            self._record_term(node.value, node.lineno, "string literal")

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name == "random" or alias.name.startswith("random."):
                self._record_det(
                    node.lineno,
                    "DET-001",
                    "Forbidden 'random' module import; use named scene RNG streams instead",
                )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module == "random" or (node.module and node.module.startswith("random.")):
            self._record_det(
                node.lineno,
                "DET-001",
                "Forbidden 'from random import ...'; use named scene RNG streams instead",
            )

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_BUILTINS:
            self._record_det(
                node.lineno,
                "SEC-001",
                f"Forbidden dynamic code builtin '{node.func.id}()'",
            )
        self.generic_visit(node)


def scan_file(path: Path) -> list[LintIssue]:
    """Parse and lint a single Python source file."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    parents = _annotate_parents(tree)
    visitor = _AgnosticismVisitor(path, source.splitlines(), parents)
    visitor.visit(tree)
    return visitor.issues


def iter_target_files(root: Path) -> list[Path]:
    """Collect Python files under backend/app target packages or an explicit path."""
    if root.is_file():
        return [root]
    app_dir = root / "backend" / "app"
    if app_dir.is_dir():
        files: list[Path] = []
        for sub in TARGET_SUBDIRS:
            subdir = app_dir / sub
            if subdir.is_dir():
                files.extend(sorted(subdir.rglob("*.py")))
        return files
    return sorted(root.rglob("*.py"))


def run_lint(target: Path) -> list[LintIssue]:
    """Run agnosticism and determinism checks against all files under target."""
    issues: list[LintIssue] = []
    for py_file in iter_target_files(target):
        issues.extend(scan_file(py_file))
    return issues


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for Golden Rule #1 & determinism CI gate."""
    parser = argparse.ArgumentParser(
        description="Lint engine modules for agnosticism and determinism."
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Repository root or directory/file to scan.",
    )
    args = parser.parse_args(argv)
    issues = run_lint(args.path.resolve())
    for issue in issues:
        print(issue.format(), file=sys.stderr)
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
