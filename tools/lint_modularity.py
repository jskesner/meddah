"""CI linter enforcing Golden Rule #4 (§1.0 MeddahModule manifests, RAW defaults, independence)."""

from __future__ import annotations

import argparse
import ast
import sys
from dataclasses import dataclass
from pathlib import Path

RAW_DEFAULT_GUARD_FIELDS: frozenset[str] = frozenset(
    {
        "fudge_rolls",
        "auto_rescue",
        "anti_tpk_override",
        "prevent_tpk",
        "enable_mercy_override",
    }
)

OPTIONAL_ROOT_DIRS: tuple[str, ...] = (
    "systems",
    "world_gen",
    "vtt",
    "agents",
    "multiplayer",
    "media",
    "safety",
    "ingestion",
)

ISOLATED_SIBLING_DIRS: frozenset[str] = frozenset({"systems", "world_gen"})
SHARED_HELPER_NAMES: frozenset[str] = frozenset(
    {"__init__", "base", "contracts", "common", "types"}
)


@dataclass(frozen=True)
class ModularityIssue:
    """Represents a single §1.0 modularity or RAW-default violation."""

    path: Path
    line: int
    rule: str
    detail: str

    def format(self) -> str:
        """Render diagnostic in compiler-style file:line format."""
        return f"{self.path}:{self.line}: [{self.rule}] {self.detail}"


def _line_has_marker(lines: list[str], lineno: int, marker: str) -> bool:
    if 1 <= lineno <= len(lines):
        return marker in lines[lineno - 1]
    return False


def _is_true_literal(node: ast.AST | None) -> bool:
    return isinstance(node, ast.Constant) and node.value is True


def _maybe_add_raw_issue(
    issues: list[ModularityIssue],
    path: Path,
    lines: list[str],
    name: str,
    default_node: ast.AST | None,
    lineno: int,
) -> None:
    if (
        name in RAW_DEFAULT_GUARD_FIELDS
        and _is_true_literal(default_node)
        and not _line_has_marker(lines, lineno, "raw-default-allow")
    ):
        issues.append(
            ModularityIssue(
                path=path,
                line=lineno,
                rule="MOD-002",
                detail=f"Outcome-altering default '{name}=True' violates RAW default policy",
            )
        )


def _check_raw_defaults(path: Path, tree: ast.AST, lines: list[str]) -> list[ModularityIssue]:
    """Ensure outcome-altering convenience flags never default to True."""
    issues: list[ModularityIssue] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    _maybe_add_raw_issue(issues, path, lines, target.id, node.value, node.lineno)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            _maybe_add_raw_issue(issues, path, lines, node.target.id, node.value, node.lineno)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            all_args = list(node.args.posonlyargs) + list(node.args.args)
            defaults: list[ast.expr | None] = [None] * (
                len(all_args) - len(node.args.defaults)
            ) + list(node.args.defaults)
            for arg, default in zip(all_args, defaults, strict=True):
                _maybe_add_raw_issue(issues, path, lines, arg.arg, default, node.lineno)
            for kwarg, default in zip(node.args.kwonlyargs, node.args.kw_defaults, strict=True):
                _maybe_add_raw_issue(issues, path, lines, kwarg.arg, default, node.lineno)
    return issues


def _check_manifest_presence(path: Path, tree: ast.AST) -> list[ModularityIssue]:
    """Require MODULE_MANIFEST when a file registers module hooks or inherits MeddahModule."""
    has_registration = False
    has_manifest = False
    reg_line = 1

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for base in node.bases:
                if isinstance(base, ast.Name) and base.id == "MeddahModule":
                    has_registration = True
                    reg_line = node.lineno
        elif isinstance(node, ast.FunctionDef) and node.name == "register_module":
            has_registration = True
            reg_line = node.lineno
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "MODULE_MANIFEST":
                    has_manifest = True
                elif isinstance(target, ast.Name) and target.id == "MODULE_PROVIDES":
                    has_registration = True
                    reg_line = node.lineno
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "MODULE_MANIFEST"
        ):
            has_manifest = True

    if has_registration and not has_manifest:
        return [
            ModularityIssue(
                path=path,
                line=reg_line,
                rule="MOD-001",
                detail="Module registers capabilities/hooks without defining MODULE_MANIFEST",
            )
        ]
    return []


def _check_sibling_imports(path: Path, tree: ast.AST, lines: list[str]) -> list[ModularityIssue]:
    """Detect undocumented direct imports between sibling optional modules."""
    parent_pkg = path.parent.name
    if parent_pkg not in ISOLATED_SIBLING_DIRS or path.stem in SHARED_HELPER_NAMES:
        return []

    issues: list[ModularityIssue] = []
    pkg_exact = f"app.{parent_pkg}"
    prefix = f"{pkg_exact}."

    for node in ast.walk(tree):
        if _line_has_marker(lines, getattr(node, "lineno", 0), "module-dep-declared"):
            continue
        if isinstance(node, ast.ImportFrom):
            targets: list[str] = []
            if (node.level == 1 and node.module is None) or node.module == pkg_exact:
                targets = [alias.name.split(".")[0] for alias in node.names]
            elif node.level == 1 and node.module:
                targets = [node.module.split(".")[0]]
            elif node.module and node.module.startswith(prefix):
                targets = [node.module.removeprefix(prefix).split(".")[0]]
            for target_mod in targets:
                if target_mod and target_mod not in SHARED_HELPER_NAMES and target_mod != path.stem:
                    issues.append(
                        ModularityIssue(
                            path=path,
                            line=node.lineno,
                            rule="MOD-003",
                            detail=f"Direct sibling import '{target_mod}' inside '{parent_pkg}'",
                        )
                    )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(prefix):
                    candidate = alias.name.removeprefix(prefix).split(".")[0]
                    if (
                        candidate
                        and candidate not in SHARED_HELPER_NAMES
                        and candidate != path.stem
                    ):
                        issues.append(
                            ModularityIssue(
                                path=path,
                                line=node.lineno,
                                rule="MOD-003",
                                detail=(
                                    f"Direct sibling import '{alias.name}' inside '{parent_pkg}'"
                                ),
                            )
                        )
    return issues


def scan_file(path: Path) -> list[ModularityIssue]:
    """Parse and validate a single optional-module Python file."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    lines = source.splitlines()
    return [
        *_check_manifest_presence(path, tree),
        *_check_raw_defaults(path, tree, lines),
        *_check_sibling_imports(path, tree, lines),
    ]


def iter_optional_files(root: Path) -> list[Path]:
    """Collect optional-module Python files under backend/app or a given path."""
    if root.is_file():
        return [root]
    app_dir = root / "backend" / "app"
    if app_dir.is_dir():
        files: list[Path] = []
        for sub in OPTIONAL_ROOT_DIRS:
            subdir = app_dir / sub
            if subdir.is_dir():
                files.extend(sorted(subdir.rglob("*.py")))
        return files
    return sorted(root.rglob("*.py"))


def run_lint(target: Path) -> list[ModularityIssue]:
    """Run all Golden Rule #4 checks across target."""
    issues: list[ModularityIssue] = []
    for py_file in iter_optional_files(target):
        issues.extend(scan_file(py_file))
    return issues


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for §1.0 Modularity CI gate."""
    parser = argparse.ArgumentParser(
        description="Lint optional Meddah modules for §1.0 compliance."
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
