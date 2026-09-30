from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from capabilities.invocation import CapabilityInvocationError, invoke_capability
from capabilities.models import CapabilityErrorCategory, CapabilityManifest, TrustLevel, ValidationStatus
from capabilities.registry import CapabilityRegistry


def test_cadquery_core_registered(tmp_path) -> None:
    registry = CapabilityRegistry(tmp_path / "caps.json")

    core = registry.get("cadquery_core")

    assert core is not None
    assert core.trust_level == TrustLevel.CORE
    assert core.enabled is True
    assert "create_box" in core.supported_operations


def test_enable_disable_and_trust_enforcement(tmp_path) -> None:
    registry = CapabilityRegistry(tmp_path / "caps.json")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "capability_id": "example_gear_tool",
                "name": "Gear Generator",
                "version": "1.0",
                "provider_type": "external",
                "source": "manual_manifest",
                "supported_operations": ["gear"],
                "required_dependencies": [],
                "trust_level": "EXPERIMENTAL",
            }
        ),
        encoding="utf-8",
    )

    discovered = registry.discover_manifest(manifest_path)
    assert discovered.enabled is False
    assert discovered.trust_level == TrustLevel.EXPERIMENTAL
    assert registry.run_self_test("example_gear_tool").validation_status == ValidationStatus.PASSED

    with pytest.raises(ValueError, match="Experimental"):
        registry.enable("example_gear_tool")

    registry.approve("example_gear_tool")
    enabled = registry.enable("example_gear_tool")
    assert enabled.enabled is True
    assert enabled.trust_level == TrustLevel.APPROVED

    disabled = registry.disable("example_gear_tool")
    assert disabled.enabled is False
    assert disabled.trust_level == TrustLevel.DISABLED


def test_invalid_manifest_rejected() -> None:
    with pytest.raises(ValidationError):
        CapabilityManifest.model_validate({"capability_id": "bad"})


def test_enabled_for_generation_excludes_experimental(tmp_path) -> None:
    registry = CapabilityRegistry(tmp_path / "caps.json")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "capability_id": "experimental_tool",
                "name": "Experimental Tool",
                "version": "1.0",
                "supported_operations": ["gear"],
                "trust_level": "EXPERIMENTAL",
            }
        ),
        encoding="utf-8",
    )
    registry.discover_manifest(manifest_path)

    enabled_ids = {capability.capability_id for capability in registry.enabled_for_generation()}

    assert "cadquery_core" in enabled_ids
    assert "experimental_tool" not in enabled_ids


def test_local_spur_gear_discovery_approval_enable_and_invoke(tmp_path) -> None:
    registry = CapabilityRegistry(tmp_path / "caps.json")

    discovered = registry.discover("local_adapters")[0]

    assert discovered.capability_id == "local.spur_gear_generator"
    assert discovered.enabled is False
    assert discovered.trust_level == TrustLevel.EXPERIMENTAL
    assert registry.run_self_test(discovered.capability_id).validation_status == ValidationStatus.PASSED

    approved = registry.approve(discovered.capability_id, notes="test approval")
    assert approved.trust_level == TrustLevel.APPROVED
    assert approved.enabled is False

    registry.enable(discovered.capability_id)
    response = invoke_capability(
        discovered.capability_id,
        {"module_mm": 1.0, "teeth": 18, "thickness_mm": 4.0, "bore_diameter_mm": 3.0},
        registry=registry,
    )

    assert response.result["result_type"] == "geometry"
    assert response.result["step_path"].endswith(".step")
    assert response.result["stl_path"].endswith(".stl")
    assert registry.get(discovered.capability_id).metrics.success_count == 1


def test_invocation_gate_rejects_disabled_and_invalid_input(tmp_path) -> None:
    registry = CapabilityRegistry(tmp_path / "caps.json")
    capability = registry.discover_local_adapter("spur_gear_generator")

    with pytest.raises(CapabilityInvocationError, match="disabled") as disabled:
        invoke_capability(capability.capability_id, {}, registry=registry)
    assert disabled.value.category == CapabilityErrorCategory.PERMISSION_FAILURE

    registry.run_self_test(capability.capability_id)
    registry.approve(capability.capability_id)
    registry.enable(capability.capability_id)

    with pytest.raises(CapabilityInvocationError, match="Missing required input field"):
        invoke_capability(capability.capability_id, {"module_mm": 1.0}, registry=registry)


def test_checksum_change_marks_capability_for_retest(tmp_path) -> None:
    registry = CapabilityRegistry(tmp_path / "caps.json")
    manifest_path = tmp_path / "manifest.json"
    manifest = {
        "capability_id": "changing_tool",
        "name": "Changing Tool",
        "version": "1.0",
        "supported_operations": ["demo"],
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    registry.discover_manifest(manifest_path)
    registry.run_self_test("changing_tool")
    registry.approve("changing_tool")
    registry.enable("changing_tool")

    manifest["description"] = "changed"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    changed = registry.discover_manifest(manifest_path)

    assert changed.validation_status == ValidationStatus.NEEDS_RETEST
    assert changed.enabled is False


def test_mcp_mock_discovery_registers_experimental_tools(tmp_path) -> None:
    config_path = tmp_path / "mcp_servers.json"
    tools_path = tmp_path / "tools.json"
    tools_path.write_text(
        json.dumps(
            {
                "tools": [
                    {
                        "name": "generate_gear",
                        "description": "Mock gear tool",
                        "input_schema": {"type": "object", "required": ["teeth"], "properties": {"teeth": {"type": "integer"}}},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    config_path.write_text(
        json.dumps(
            {
                "servers": [
                    {
                        "id": "engineering_tools",
                        "name": "Engineering Tools",
                        "transport": "stdio",
                        "enabled": True,
                        "mock_tools_path": str(tools_path),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    import capabilities.mcp as mcp_module
    import capabilities.registry as registry_module

    old_registry_path = registry_module.CONFIG.mcp_servers_config_path
    old_mcp_path = mcp_module.CONFIG.mcp_servers_config_path
    try:
        object.__setattr__(registry_module.CONFIG, "mcp_servers_config_path", config_path)
        object.__setattr__(mcp_module.CONFIG, "mcp_servers_config_path", config_path)
        registry = CapabilityRegistry(tmp_path / "caps.json")
        discovered = registry.discover("mcp:engineering_tools")
    finally:
        object.__setattr__(registry_module.CONFIG, "mcp_servers_config_path", old_registry_path)
        object.__setattr__(mcp_module.CONFIG, "mcp_servers_config_path", old_mcp_path)

    assert discovered[0].capability_id == "engineering_tools.generate_gear"
    assert discovered[0].trust_level == TrustLevel.EXPERIMENTAL
    assert discovered[0].enabled is False
