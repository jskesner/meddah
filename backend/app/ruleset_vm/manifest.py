"""Strict Layer-0 package manifest schemas for Meddah content archives."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PackageType = Literal[
    "ruleset",
    "world",
    "campaign",
    "character",
    "tileset",
    "theme",
    "profile",
    "competition",
]


class PackageManifest(BaseModel):
    """Authoritative metadata header for portable Meddah archives."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(
        default="0.1.0",
        description="Semantic version of the package archive format.",
    )
    package_type: PackageType = Field(
        description="Archive kind (.rpgrules, .rpgworld, .rpgcampaign, etc.).",
    )
    package_id: str = Field(
        min_length=1,
        description="Stable slug identifier for the packaged resource.",
    )
    name: str = Field(
        min_length=1,
        description="Human-readable package display name.",
    )
    version: str = Field(
        min_length=1,
        description="Creator-assigned semantic version of this package.",
    )
    description: str = Field(
        default="",
        description="Optional short description of the package contents.",
    )
    ruleset_hash: str | None = Field(
        default=None,
        description="Optional SHA-256 hash of the bound source ruleset schema.",
    )
    authors: tuple[str, ...] = Field(
        default=(),
        description="Package authors or maintainers.",
    )
    license: str = Field(
        default="All Rights Reserved",
        description="Creator license identifier for this user data package.",
    )
