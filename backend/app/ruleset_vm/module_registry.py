"""Module Registry, Capability Gating & Dormancy Architecture (§1.0 / Golden Rule #4)."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ModuleState = Literal["dormant", "available", "active"]
ModuleScope = Literal["campaign", "session", "player_local"]
SeatRole = Literal["host", "gm", "co_gm", "host_player", "player", "spectator"]
SafeBoundary = Literal["next_scene_rest_or_session", "end_of_current_turn", "immediate"]
SubOptionValue = str | bool | int


class ModuleProvides(BaseModel):
    """UI surfaces, commands, hooks, and schema extensions exposed while a module is active."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    commands: tuple[str, ...] = ()
    ui_panels: tuple[str, ...] = ()
    event_hooks: tuple[str, ...] = ()
    schema_blocks: tuple[str, ...] = ()
    studio_editors: tuple[str, ...] = ()

    def merged_with(self, other: ModuleProvides) -> ModuleProvides:
        """Return deduplicated sorted union of two ModuleProvides declarations."""
        return ModuleProvides(
            commands=tuple(sorted(set(self.commands) | set(other.commands))),
            ui_panels=tuple(sorted(set(self.ui_panels) | set(other.ui_panels))),
            event_hooks=tuple(sorted(set(self.event_hooks) | set(other.event_hooks))),
            schema_blocks=tuple(sorted(set(self.schema_blocks) | set(other.schema_blocks))),
            studio_editors=tuple(sorted(set(self.studio_editors) | set(other.studio_editors))),
        )


class MeddahModuleManifest(BaseModel):
    """Declarative manifest required by every optional Meddah subsystem (§1.0)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    module_id: str = Field(min_length=1)
    spec_section: str = Field(min_length=1)
    label: str = Field(min_length=1)
    requires_primitives: tuple[str, ...] = ()
    requires_any_primitive: tuple[str, ...] = ()
    requires_modules: tuple[str, ...] = ()
    enhances_modules: tuple[str, ...] = ()
    provides: ModuleProvides = Field(default_factory=ModuleProvides)
    scope: ModuleScope = "campaign"
    ai_dependency: Literal["none"] = "none"


class ModuleProfile(BaseModel):
    """Portable bundle of module enable flags and sub-options (contains zero rules mechanics)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    profile_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    description: str = ""
    enabled_modules: tuple[str, ...] = ()
    sub_options: dict[str, dict[str, SubOptionValue]] = Field(default_factory=dict)


class ModuleOverrideEvent(BaseModel):
    """Audited host/GM override toggling a module at a safe replay boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    module_id: str = Field(min_length=1)
    enabled: bool
    sub_options: dict[str, SubOptionValue] = Field(default_factory=dict)
    boundary: SafeBoundary = "next_scene_rest_or_session"
    actor_seat_id: str = Field(min_length=1)
    reason: str = ""


class ModuleStatusSnapshot(BaseModel):
    """Resolved module availability and active state for UI and capability gating."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    module_id: str
    state: ModuleState
    enabled_requested: bool
    missing_primitives: tuple[str, ...] = ()
    missing_modules: tuple[str, ...] = ()
    sub_options: dict[str, SubOptionValue] = Field(default_factory=dict)


MINIMAL_PROFILE = ModuleProfile(
    profile_id="theater_of_mind_minimal",
    label="Theater of the Mind / Minimal",
    description="Core VM + AI/Deterministic GM + Capabilities Deck.",
    enabled_modules=("gm_director", "quests", "safety_accessibility"),
)

CLASSIC_TABLETOP_PROFILE = ModuleProfile(
    profile_id="classic_tabletop",
    label="Classic Tabletop",
    description="Minimal + Tactical VTT, Rest/Downtime, Loot, Quests, and Companions.",
    enabled_modules=(
        "gm_director",
        "tactical_vtt",
        "rest_downtime",
        "loot",
        "quests",
        "companions",
        "safety_accessibility",
    ),
)

RAW_PROTECTED_SUB_OPTIONS: dict[str, dict[str, SubOptionValue]] = {
    "gm_mercy": {
        "encounter_scaling": "static_raw",
        "fudge_rolls": False,
        "anti_tpk_override": False,
        "hint_mode": "raw_checks_only",
    }
}


class ModuleRegistry:
    """Manages §1.0 module manifests, 3-state dormancy resolution, RBAC, and sandbox cloning."""

    def __init__(self) -> None:
        self._manifests: dict[str, MeddahModuleManifest] = {}
        self._enabled: set[str] = set()
        self._sub_options: dict[str, dict[str, SubOptionValue]] = {}
        self._queued_overrides: list[ModuleOverrideEvent] = []

    def register(self, manifest: MeddahModuleManifest) -> None:
        """Register a module manifest by module_id."""
        if manifest.module_id in self._manifests:
            raise ValueError(f"Duplicate module_id registration: '{manifest.module_id}'")
        self._manifests[manifest.module_id] = manifest

    def manifests(self) -> dict[str, MeddahModuleManifest]:
        """Return registered module manifests keyed by module_id."""
        return dict(self._manifests)

    def _missing_primitives(
        self,
        manifest: MeddahModuleManifest,
        declared_set: frozenset[str],
    ) -> tuple[str, ...]:
        missing = [p for p in manifest.requires_primitives if p not in declared_set]
        if manifest.requires_any_primitive and not (
            set(manifest.requires_any_primitive) & declared_set
        ):
            missing.append(f"any_of({','.join(manifest.requires_any_primitive)})")
        return tuple(missing)

    def resolve_status(
        self,
        module_id: str,
        declared_primitives: Iterable[str],
        *,
        _visiting: set[str] | None = None,
    ) -> ModuleStatusSnapshot:
        """Resolve a module to dormant, available, or active based on primitives & deps."""
        manifest = self._manifests.get(module_id)
        if manifest is None:
            raise KeyError(f"Unknown module_id '{module_id}'")

        visiting: set[str] = set() if _visiting is None else set(_visiting)
        if module_id in visiting:
            raise ValueError(f"Circular module dependency involving '{module_id}'")
        visiting.add(module_id)

        declared_set = frozenset(declared_primitives)
        missing_prims = self._missing_primitives(manifest, declared_set)
        enabled_req = module_id in self._enabled
        sub_opts = dict(self._sub_options.get(module_id, {}))

        if missing_prims:
            return ModuleStatusSnapshot(
                module_id=module_id,
                state="dormant",
                enabled_requested=enabled_req,
                missing_primitives=missing_prims,
                sub_options=sub_opts,
            )

        missing_deps: list[str] = []
        any_dep_dormant = False
        for dep_id in manifest.requires_modules:
            if dep_id not in self._manifests:
                missing_deps.append(dep_id)
                any_dep_dormant = True
                continue
            dep_snap = self.resolve_status(dep_id, declared_set, _visiting=visiting)
            if dep_snap.state == "dormant":
                missing_deps.append(dep_id)
                any_dep_dormant = True
            elif dep_snap.state != "active":
                missing_deps.append(dep_id)

        if any_dep_dormant:
            state: ModuleState = "dormant"
        elif enabled_req and not missing_deps:
            state = "active"
        else:
            state = "available"

        return ModuleStatusSnapshot(
            module_id=module_id,
            state=state,
            enabled_requested=enabled_req,
            missing_primitives=(),
            missing_modules=tuple(missing_deps),
            sub_options=sub_opts,
        )

    def resolve_all(self, declared_primitives: Iterable[str]) -> dict[str, ModuleStatusSnapshot]:
        """Resolve statuses for all registered modules in sorted module_id order."""
        declared_tuple = tuple(declared_primitives)
        return {
            mod_id: self.resolve_status(mod_id, declared_tuple)
            for mod_id in sorted(self._manifests)
        }

    def active_provides(self, declared_primitives: Iterable[str]) -> ModuleProvides:
        """Return only commands/UI/hooks from modules currently resolved as active."""
        merged = ModuleProvides()
        for snap in self.resolve_all(declared_primitives).values():
            if snap.state == "active":
                merged = merged.merged_with(self._manifests[snap.module_id].provides)
        return merged

    def dependent_modules(self, module_id: str) -> tuple[str, ...]:
        """List registered module IDs that directly declare a hard dependency on module_id."""
        return tuple(
            sorted(mid for mid, man in self._manifests.items() if module_id in man.requires_modules)
        )

    def check_toggle_permission(
        self,
        module_id: str,
        *,
        seat_role: SeatRole,
        is_server_admin: bool,
        can_toggle_campaign_modules: bool = False,
    ) -> bool:
        """Enforce §1.0 Host-controlled module toggling permissions."""
        manifest = self._manifests.get(module_id)
        if manifest is None:
            raise KeyError(f"Unknown module_id '{module_id}'")
        if manifest.scope == "player_local":
            return True
        if is_server_admin or seat_role == "host":
            return True
        return seat_role in {"gm", "co_gm"} and can_toggle_campaign_modules

    def set_enabled(
        self,
        module_id: str,
        enabled: bool,
        sub_options: dict[str, SubOptionValue] | None = None,
    ) -> None:
        """Directly enable or disable a registered module and optional sub-options."""
        if module_id not in self._manifests:
            raise KeyError(f"Unknown module_id '{module_id}'")
        if enabled:
            self._enabled.add(module_id)
        else:
            self._enabled.discard(module_id)
        if sub_options is not None:
            self._sub_options[module_id] = dict(sub_options)

    def apply_profile(self, profile: ModuleProfile, *, include_raw_defaults: bool = True) -> None:
        """Apply a toggle-only ModuleProfile without touching campaign rules."""
        self._enabled = {mid for mid in profile.enabled_modules if mid in self._manifests}
        if include_raw_defaults:
            for mod_id, defaults in RAW_PROTECTED_SUB_OPTIONS.items():
                if mod_id in self._manifests and mod_id not in self._sub_options:
                    self._sub_options[mod_id] = dict(defaults)
        for mod_id, opts in profile.sub_options.items():
            if mod_id in self._manifests:
                self._sub_options[mod_id] = dict(opts)

    def queue_override(
        self,
        override: ModuleOverrideEvent,
        *,
        seat_role: SeatRole,
        is_server_admin: bool,
        can_toggle_campaign_modules: bool = False,
    ) -> list[ModuleOverrideEvent]:
        """Queue or immediately apply an audited MODULE_OVERRIDE event after RBAC check."""
        allowed = self.check_toggle_permission(
            override.module_id,
            seat_role=seat_role,
            is_server_admin=is_server_admin,
            can_toggle_campaign_modules=can_toggle_campaign_modules,
        )
        if not allowed:
            raise PermissionError(
                f"Seat role '{seat_role}' lacks permission to toggle '{override.module_id}'."
            )
        if override.boundary == "immediate":
            self.set_enabled(
                override.module_id,
                override.enabled,
                dict(override.sub_options) if override.sub_options else None,
            )
            return [override]
        self._queued_overrides.append(override)
        return []

    def pending_overrides(self) -> tuple[ModuleOverrideEvent, ...]:
        """Return module changes awaiting a safe turn/scene boundary."""
        return tuple(self._queued_overrides)

    def flush_boundary(self, boundary: SafeBoundary) -> list[ModuleOverrideEvent]:
        """Apply overrides scheduled for the reached safe boundary and return applied events."""
        applied: list[ModuleOverrideEvent] = []
        remaining: list[ModuleOverrideEvent] = []
        for item in self._queued_overrides:
            if boundary == "next_scene_rest_or_session" or item.boundary == boundary:
                self.set_enabled(
                    item.module_id,
                    item.enabled,
                    dict(item.sub_options) if item.sub_options else None,
                )
                applied.append(item)
            else:
                remaining.append(item)
        self._queued_overrides = remaining
        return applied

    def clone_sandbox(self) -> ModuleRegistry:
        """Create an isolated Copy-on-Write sandbox clone for non-disruptive testing."""
        sandbox = ModuleRegistry()
        sandbox._manifests = dict(self._manifests)
        sandbox._enabled = set(self._enabled)
        sandbox._sub_options = {k: dict(v) for k, v in self._sub_options.items()}
        sandbox._queued_overrides = list(self._queued_overrides)
        return sandbox
