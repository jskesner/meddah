"""Generate authoritative JSON Schemas from backend Pydantic models."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pydantic import BaseModel

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.mud_parser import (  # noqa: E402
    CommunicationMediumBlock,
    CustomEmoteBlock,
    CustomMudCommandBlock,
    LanguageBlock,
)
from app.ruleset_vm import (  # noqa: E402
    AdvancementGraphSpec,
    InventoryGraphState,
    PackageManifest,
    RulesetSchema,
    VmEvent,
)

SCHEMA_MODELS: dict[str, type[BaseModel]] = {
    "advancement": AdvancementGraphSpec,
    "comms_medium": CommunicationMediumBlock,
    "custom_command": CustomMudCommandBlock,
    "custom_emote": CustomEmoteBlock,
    "event": VmEvent,
    "inventory": InventoryGraphState,
    "language": LanguageBlock,
    "manifest": PackageManifest,
    "ruleset": RulesetSchema,
}


def render_schema(model: type[BaseModel]) -> str:
    """Serialize a Pydantic model into deterministic formatted JSON Schema text."""
    return json.dumps(model.model_json_schema(), indent=2, sort_keys=True) + "\n"


def sync_schemas(schemas_dir: Path, check_only: bool) -> list[str]:
    """Write JSON schema files or verify existing files match Pydantic models."""
    errors: list[str] = []
    if not check_only:
        schemas_dir.mkdir(parents=True, exist_ok=True)

    for name, model in sorted(SCHEMA_MODELS.items()):
        target = schemas_dir / f"{name}.schema.json"
        expected = render_schema(model)
        if check_only:
            if not target.is_file():
                errors.append(f"Missing generated schema: {target}")
                continue
            actual = target.read_text(encoding="utf-8")
            if actual != expected:
                errors.append(f"Stale schema file: {target} (run tools/generate_types.py)")
        else:
            target.write_text(expected, encoding="utf-8")
    return errors


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for JSON Schema generation and staleness verification."""
    parser = argparse.ArgumentParser(description="Generate or verify JSON Schemas from Pydantic.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify schemas are up to date without writing files.",
    )
    parser.add_argument(
        "--schemas-dir",
        type=Path,
        default=REPO_ROOT / "schemas",
        help="Destination directory for .schema.json files.",
    )
    args = parser.parse_args(argv)
    errors = sync_schemas(args.schemas_dir.resolve(), check_only=args.check)
    for err in errors:
        print(err, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
