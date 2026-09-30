from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from capabilities.models import (
    CapabilityManifest,
    CapabilityMetrics,
    CapabilityRecord,
    DiscoverySource,
    DiscoverySourceType,
    ProviderType,
    TrustLevel,
    ValidationStatus,
)
from config import CONFIG


CORE_OPERATIONS = [
    "create_box",
    "create_cylinder",
    "create_sketch",
    "create_sketch_rectangle",
    "create_sketch_circle",
    "extrude",
    "revolve",
    "cut_hole",
    "cut_extrude",
    "loft",
    "sweep",
    "shell",
    "through_hole",
    "blind_hole",
    "counterbore_hole",
    "countersink_hole",
    "boss",
    "rib",
    "rectangular_hole_pattern",
    "circular_hole_pattern",
    "boolean_union",
    "boolean_cut",
    "fillet",
    "chamfer",
    "linear_pattern",
    "circular_pattern",
    "mirror",
]


def core_cadquery_capability() -> CapabilityRecord:
    return CapabilityRecord(
        capability_id="cadquery_core",
        name="CadQuery Core Engine",
        version="1.0",
        description="Built-in deterministic CadQuery operation executor.",
        source="built_in",
        provider_type=ProviderType.CORE,
        supported_operations=CORE_OPERATIONS,
        required_dependencies=["cadquery"],
        trust_level=TrustLevel.CORE,
        enabled=True,
        validation_status=ValidationStatus.PASSED,
        discovered_at=_now(),
        last_checked_at=_now(),
        last_tested_at=_now(),
    )


def core_engineering_capability() -> CapabilityRecord:
    return CapabilityRecord(
        capability_id="engineering_core",
        name="SHAH Engineering Analysis Core",
        version="1.0",
        description="Built-in deterministic geometry metrics, unit conversion, material mass, and DFM warning engine.",
        source="built_in",
        provider_type=ProviderType.CORE,
        supported_operations=[
            "geometry_metrics",
            "material_mass",
            "unit_conversion",
            "manufacturing_warnings",
        ],
        required_dependencies=["cadquery"],
        trust_level=TrustLevel.CORE,
        enabled=True,
        validation_status=ValidationStatus.PASSED,
        discovered_at=_now(),
        last_checked_at=_now(),
        last_tested_at=_now(),
    )


class CapabilityRegistry:
    """Local capability metadata registry with explicit trust and enablement."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else CONFIG.capability_registry_path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._records = self._load()
        self._records["cadquery_core"] = core_cadquery_capability()
        self._records["engineering_core"] = core_engineering_capability()

    def list(self) -> list[CapabilityRecord]:
        return sorted(self._records.values(), key=lambda record: record.capability_id)

    def get(self, capability_id: str) -> CapabilityRecord | None:
        return self._records.get(capability_id)

    def list_sources(self) -> list[DiscoverySource]:
        sources = [
            DiscoverySource(
                source_id="local_adapters",
                name="Local Developer Adapters",
                source_type=DiscoverySourceType.LOCAL_ADAPTER,
                location="capabilities/adapters",
                enabled=True,
                trusted=True,
                notes="Allowlisted local Python adapters shipped with this repository.",
            ),
            DiscoverySource(
                source_id="local_manifests",
                name="Local Capability Manifests",
                source_type=DiscoverySourceType.LOCAL_MANIFEST,
                location="capabilities/manifests",
                enabled=True,
                trusted=False,
                notes="Local JSON manifests only; discovery never installs or executes code.",
            ),
        ]
        sources.extend(_mcp_sources())
        return sources

    def discover(self, source_id: str | None = None) -> list[CapabilityRecord]:
        if source_id in {None, "local_adapters"}:
            return [self.discover_local_adapter("spur_gear_generator")]
        if source_id == "local_manifests":
            manifest_dir = Path("capabilities") / "manifests"
            if not manifest_dir.exists():
                return []
            return [self.discover_manifest(path) for path in sorted(manifest_dir.glob("*.json"))]
        if source_id and source_id.startswith("mcp:"):
            from capabilities.mcp import discover_mcp_capabilities

            records = discover_mcp_capabilities(source_id.removeprefix("mcp:"))
            return [self._upsert_discovered(record) for record in records]
        raise ValueError(f"Unknown or disabled discovery source: {source_id}")

    def discover_manifest(self, manifest_path: str | Path) -> CapabilityRecord:
        path = Path(manifest_path)
        raw = path.read_bytes()
        manifest = CapabilityManifest.model_validate_json(raw.decode("utf-8"))
        data = manifest.model_dump()
        data["source"] = str(path)
        data["checksum"] = _sha256(raw)
        return self._upsert_manifest(data)

    def discover_local_adapter(self, adapter_id: str) -> CapabilityRecord:
        if adapter_id != "spur_gear_generator":
            raise ValueError(f"Unknown local adapter: {adapter_id}")
        from capabilities.adapters.spur_gear import get_manifest

        manifest = get_manifest()
        data = manifest.model_dump()
        data["provider_type"] = ProviderType.LOCAL_ADAPTER
        data["source"] = "capabilities.adapters.spur_gear"
        data["local_adapter"] = "spur_gear_generator"
        data["checksum"] = _file_checksum(Path("capabilities") / "adapters" / "spur_gear.py")
        return self._upsert_manifest(data)

    def run_self_test(self, capability_id: str) -> CapabilityRecord:
        record = self._require(capability_id)
        status = ValidationStatus.PASSED if _self_test(record) else ValidationStatus.FAILED
        updated = record.model_copy(
            update={
                "validation_status": status,
                "last_tested_at": _now(),
                "last_checked_at": _now(),
            }
        )
        self._records[capability_id] = updated
        self._save()
        return updated

    def approve(self, capability_id: str, *, approved_by: str = "local_user", notes: str | None = None) -> CapabilityRecord:
        record = self._require(capability_id)
        if record.trust_level == TrustLevel.CORE:
            return record
        if record.validation_status != ValidationStatus.PASSED:
            raise ValueError("Capability must pass self-test before approval.")
        updated = record.model_copy(
            update={
                "trust_level": TrustLevel.APPROVED,
                "approved_at": _now(),
                "approved_by": approved_by,
                "approval_notes": notes,
            }
        )
        self._records[capability_id] = updated
        self._save()
        return updated

    def enable(self, capability_id: str) -> CapabilityRecord:
        record = self._require(capability_id)
        if record.trust_level == TrustLevel.EXPERIMENTAL:
            raise ValueError("Experimental capabilities must be approved before enabling.")
        if record.trust_level == TrustLevel.DISABLED:
            raise ValueError("Disabled capabilities cannot be enabled until trust is raised.")
        if record.validation_status != ValidationStatus.PASSED:
            raise ValueError("Capability must pass self-test before enabling.")
        updated = record.model_copy(update={"enabled": True})
        self._records[capability_id] = updated
        self._save()
        return updated

    def disable(self, capability_id: str) -> CapabilityRecord:
        record = self._require(capability_id)
        if record.trust_level == TrustLevel.CORE:
            raise ValueError("Core capabilities cannot be disabled.")
        updated = record.model_copy(update={"enabled": False, "trust_level": TrustLevel.DISABLED})
        self._records[capability_id] = updated
        self._save()
        return updated

    def enabled_for_generation(self) -> list[CapabilityRecord]:
        return [
            record
            for record in self._records.values()
            if record.enabled
            and record.trust_level in {TrustLevel.CORE, TrustLevel.APPROVED}
            and record.validation_status == ValidationStatus.PASSED
        ]

    def record_invocation(self, capability_id: str, *, success: bool, timestamp: str | None = None) -> CapabilityRecord:
        record = self._require(capability_id)
        now = timestamp or _now()
        metrics = record.metrics.model_copy(
            update={
                "invocation_count": record.metrics.invocation_count + 1,
                "success_count": record.metrics.success_count + (1 if success else 0),
                "failure_count": record.metrics.failure_count + (0 if success else 1),
                "last_success_at": now if success else record.metrics.last_success_at,
                "last_failure_at": record.metrics.last_failure_at if success else now,
            }
        )
        updated = record.model_copy(update={"metrics": metrics})
        self._records[capability_id] = updated
        self._save()
        return updated

    def _upsert_discovered(self, record: CapabilityRecord) -> CapabilityRecord:
        return self._upsert_manifest(record.model_dump())

    def _upsert_manifest(self, data: dict[str, Any]) -> CapabilityRecord:
        capability_id = str(data["capability_id"])
        existing = self._records.get(capability_id)
        if data.get("trust_level") == TrustLevel.CORE:
            data["trust_level"] = TrustLevel.EXPERIMENTAL
        data["enabled"] = False if existing is None else existing.enabled
        data["validation_status"] = ValidationStatus.UNTESTED
        data["discovered_at"] = existing.discovered_at if existing else _now()
        data["last_checked_at"] = _now()
        data["last_tested_at"] = existing.last_tested_at if existing else None
        data["approved_at"] = existing.approved_at if existing else None
        data["approved_by"] = existing.approved_by if existing else None
        data["approval_notes"] = existing.approval_notes if existing else None
        data["metrics"] = existing.metrics if existing else CapabilityMetrics()

        if existing and (existing.version != data.get("version") or existing.checksum != data.get("checksum")):
            data["enabled"] = False
            data["validation_status"] = ValidationStatus.NEEDS_RETEST
            if existing.trust_level == TrustLevel.APPROVED:
                data["trust_level"] = TrustLevel.EXPERIMENTAL

        record = CapabilityRecord.model_validate(data)
        self._records[record.capability_id] = record
        self._save()
        return record

    def _require(self, capability_id: str) -> CapabilityRecord:
        record = self.get(capability_id)
        if record is None:
            raise ValueError(f"Unknown capability: {capability_id}")
        return record

    def _load(self) -> dict[str, CapabilityRecord]:
        if not self.path.exists():
            return {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            return {
                item["capability_id"]: CapabilityRecord.model_validate(item)
                for item in raw.get("capabilities", [])
            }
        except (OSError, ValueError, ValidationError):
            return {}

    def _save(self) -> None:
        non_core = [
            record.model_dump(mode="json")
            for record in self._records.values()
            if record.trust_level != TrustLevel.CORE
        ]
        self.path.write_text(json.dumps({"capabilities": non_core}, indent=2), encoding="utf-8")


def _self_test(record: CapabilityRecord) -> bool:
    if not record.capability_id or not record.name:
        return False
    if any(operation.strip() == "" for operation in record.supported_operations):
        return False
    if record.provider_type == ProviderType.CORE:
        return True
    if not _schema_parseable(record.input_schema) or not _schema_parseable(record.output_schema):
        return False
    if record.provider_type == ProviderType.LOCAL_ADAPTER and record.local_adapter == "spur_gear_generator":
        from capabilities.adapters.spur_gear import run_self_test

        return run_self_test()
    return True


def _schema_parseable(schema: dict[str, Any]) -> bool:
    if not schema:
        return True
    return schema.get("type") in {None, "object"}


def _mcp_sources() -> list[DiscoverySource]:
    path = CONFIG.mcp_servers_config_path
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return []
    sources: list[DiscoverySource] = []
    for server in data.get("servers", []):
        if not server.get("enabled", False):
            continue
        sources.append(
            DiscoverySource(
                source_id=f"mcp:{server['id']}",
                name=server.get("name", server["id"]),
                source_type=DiscoverySourceType.MCP_SERVER,
                location=server.get("transport", "stdio"),
                enabled=True,
                trusted=bool(server.get("trusted", False)),
                notes="Configured MCP server. Discovery lists tools as experimental and disabled.",
            )
        )
    return sources


def _file_checksum(path: Path) -> str:
    return _sha256(path.read_bytes())


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _now() -> str:
    return datetime.now(UTC).isoformat()
