"""Validate ROADMAP.md YAML front-matter, statuses, checkboxes, and relative links."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

ALLOWED_STATUSES: frozenset[str] = frozenset({"Planned", "In Progress", "Done", "Deferred"})
REQUIRED_PHASE_KEYS: frozenset[str] = frozenset(
    {"id", "name", "mvp", "status", "target_release", "spec"}
)
LINK_PATTERN = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def extract_front_matter(text: str) -> tuple[dict[str, object], str]:
    """Split YAML front-matter header from Markdown body."""
    if not text.startswith("---\n"):
        raise ValueError("ROADMAP.md must start with YAML front-matter '---'")
    end_idx = text.find("\n---\n", 4)
    if end_idx == -1:
        raise ValueError("ROADMAP.md missing closing front-matter '---'")
    raw_yaml = text[4:end_idx]
    body = text[end_idx + 5 :]
    data = yaml.safe_load(raw_yaml)
    if not isinstance(data, dict):
        raise ValueError("ROADMAP.md YAML front-matter must be a mapping")
    return data, body


def validate_roadmap(roadmap_path: Path) -> list[str]:
    """Validate ROADMAP.md structure, statuses, spec paths, and Markdown links."""
    errors: list[str] = []
    if not roadmap_path.is_file():
        return [f"Roadmap file not found: {roadmap_path}"]

    repo_root = roadmap_path.parent
    text = roadmap_path.read_text(encoding="utf-8")

    try:
        front_matter, body = extract_front_matter(text)
    except (ValueError, yaml.YAMLError) as exc:
        return [f"Front-matter error: {exc}"]

    if front_matter.get("project") != "meddah":
        errors.append(f"Expected project 'meddah', found {front_matter.get('project')!r}")

    phases = front_matter.get("phases")
    if not isinstance(phases, list) or not phases:
        errors.append("Front-matter 'phases' must be a non-empty list")
        return errors

    seen_ids: set[str] = set()
    for idx, phase in enumerate(phases):
        if not isinstance(phase, dict):
            errors.append(f"Phase entry #{idx} must be a mapping")
            continue
        missing = REQUIRED_PHASE_KEYS - set(phase.keys())
        if missing:
            errors.append(f"Phase entry #{idx} missing keys: {sorted(missing)}")
            continue

        phase_id = str(phase["id"])
        if phase_id in seen_ids:
            errors.append(f"Duplicate phase id: {phase_id}")
        seen_ids.add(phase_id)

        if not isinstance(phase["mvp"], bool):
            errors.append(f"Phase {phase_id}: 'mvp' must be boolean")

        status = str(phase["status"])
        if status not in ALLOWED_STATUSES:
            errors.append(f"Phase {phase_id}: invalid status {status!r}")

        spec_rel = str(phase["spec"])
        spec_target = (repo_root / spec_rel).resolve()
        if not spec_target.exists():
            errors.append(f"Phase {phase_id}: spec file not found: {spec_rel}")

        if status == "Done":
            section_match = re.search(
                rf"^### \[{re.escape(phase_id)}\].*?(?=^### |\Z)",
                body,
                flags=re.MULTILINE | re.DOTALL,
            )
            if section_match and "- [ ]" in section_match.group(0):
                errors.append(f"Phase {phase_id} is marked 'Done' but still has unchecked items")

    for match in LINK_PATTERN.finditer(body):
        href = match.group(1).strip()
        if href.startswith(("http://", "https://", "mailto:", "#")):
            continue
        target_rel = href.split("#", 1)[0]
        if not target_rel:
            continue
        resolved = (repo_root / target_rel).resolve()
        if not resolved.exists():
            errors.append(f"Broken relative link in ROADMAP.md: {href}")

    return errors


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for validating ROADMAP.md."""
    parser = argparse.ArgumentParser(description="Validate ROADMAP.md metadata and links.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate and exit non-zero on errors (default behavior).",
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "ROADMAP.md",
        help="Path to ROADMAP.md.",
    )
    args = parser.parse_args(argv)
    errors = validate_roadmap(args.file.resolve())
    for err in errors:
        print(err, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
