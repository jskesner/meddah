"""Bootstrap verification tests for manifests, governance linters, schemas, and ROADMAP."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.ruleset_vm import PackageManifest

REPO_ROOT = Path(__file__).resolve().parents[3]
TOOLS_DIR = REPO_ROOT / "tools"


def _run_tool(script_name: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TOOLS_DIR / script_name), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.zero_ai
def test_package_manifest_validation_and_schema_sync() -> None:
    """PackageManifest validates strictly and matches schemas/manifest.schema.json."""
    manifest = PackageManifest(
        package_type="ruleset",
        package_id="classic_d20_fantasy",
        name="Classic d20 Fantasy",
        version="0.1.0",
        authors=("Meddah Contributors",),
    )
    assert manifest.schema_version == "0.1.0"
    assert manifest.package_type == "ruleset"

    with pytest.raises(ValidationError):
        PackageManifest(
            package_type="ruleset",
            package_id="bad",
            name="Bad",
            version="0.1.0",
            unknown_field="forbidden",  # type: ignore[call-arg]
        )

    schema_path = REPO_ROOT / "schemas" / "manifest.schema.json"
    assert schema_path.is_file()
    schema_data = json.loads(schema_path.read_text(encoding="utf-8"))
    assert schema_data["title"] == "PackageManifest"

    check_proc = _run_tool("generate_types.py", "--check")
    assert check_proc.returncode == 0, check_proc.stderr


@pytest.mark.zero_ai
def test_lint_agnosticism_catches_game_terms_and_determinism_violations(tmp_path: Path) -> None:
    """lint_agnosticism flags game terms, random imports, eval(), and wall-clock calls."""
    bad_file = tmp_path / "bad_module.py"
    bad_file.write_text(
        "\n".join(
            [
                "import random",
                "import time",
                "",
                "def roll_check():",
                "    max_hp = 10",
                "    armor_class = 15",
                '    _ = eval("1 + 1")',
                "    return max_hp + armor_class + int(time.time()) + random.randint(1, 6)",
            ]
        ),
        encoding="utf-8",
    )

    bad_proc = _run_tool("lint_agnosticism.py", "--path", str(bad_file))
    assert bad_proc.returncode == 1
    assert "AGN-001" in bad_proc.stderr
    assert "DET-001" in bad_proc.stderr
    assert "DET-002" in bad_proc.stderr
    assert "SEC-001" in bad_proc.stderr

    good_file = tmp_path / "good_module.py"
    good_file.write_text(
        "\n".join(
            [
                '"""Universal stat and track helper (hp mention in docstring ignored)."""',
                "",
                "def compute_track_cap(max_vitality: int, track_count: int) -> int:",
                '    state = {"vitality": max_vitality, "tracks": track_count}',
                '    return state["vitality"] * state["tracks"]',
            ]
        ),
        encoding="utf-8",
    )

    good_proc = _run_tool("lint_agnosticism.py", "--path", str(good_file))
    assert good_proc.returncode == 0, good_proc.stderr


@pytest.mark.zero_ai
def test_lint_modularity_catches_non_raw_defaults_and_sibling_imports(tmp_path: Path) -> None:
    """lint_modularity enforces RAW defaults and optional-module sibling isolation."""
    systems_dir = tmp_path / "systems"
    systems_dir.mkdir()

    bad_mod = systems_dir / "chase_engine.py"
    bad_mod.write_text(
        "\n".join(
            [
                "from app.systems import competition_engine",
                "",
                "def resolve_outcome(fudge_rolls: bool = True) -> bool:",
                "    return fudge_rolls and bool(competition_engine)",
            ]
        ),
        encoding="utf-8",
    )

    bad_proc = _run_tool("lint_modularity.py", "--path", str(bad_mod))
    assert bad_proc.returncode == 1
    assert "MOD-002" in bad_proc.stderr
    assert "MOD-003" in bad_proc.stderr

    good_mod = systems_dir / "clean_engine.py"
    good_mod.write_text(
        "\n".join(
            [
                'MODULE_MANIFEST = {"module_id": "clean_engine"}',
                "",
                "def resolve_outcome(fudge_rolls: bool = False) -> bool:",
                "    return fudge_rolls",
            ]
        ),
        encoding="utf-8",
    )

    good_proc = _run_tool("lint_modularity.py", "--path", str(good_mod))
    assert good_proc.returncode == 0, good_proc.stderr


@pytest.mark.zero_ai
def test_roadmap_and_repo_linters_pass() -> None:
    """Repository ROADMAP.md and actual backend sources pass all governance checks."""
    roadmap_proc = _run_tool("roadmap.py", "--check")
    assert roadmap_proc.returncode == 0, roadmap_proc.stderr

    agn_proc = _run_tool("lint_agnosticism.py")
    assert agn_proc.returncode == 0, agn_proc.stderr

    mod_proc = _run_tool("lint_modularity.py")
    assert mod_proc.returncode == 0, mod_proc.stderr
