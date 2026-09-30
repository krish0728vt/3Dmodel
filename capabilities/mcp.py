from __future__ import annotations

import json
from pathlib import Path

from capabilities.models import CapabilityRecord, ProviderType, TrustLevel, ValidationStatus
from config import CONFIG


def discover_mcp_capabilities(server_id: str) -> list[CapabilityRecord]:
    """Register configured MCP tool metadata without enabling or invoking tools.

    This implementation intentionally supports a mockable/static tool metadata
    file from local configuration. It does not execute arbitrary commands from
    remote metadata. A real stdio transport can be layered behind this boundary
    once the server is explicitly configured and approved.
    """

    server = _configured_server(server_id)
    if server is None:
        raise ValueError(f"MCP server is not configured or enabled: {server_id}")
    metadata_path = server.get("mock_tools_path")
    if not metadata_path:
        return []
    data = json.loads(Path(metadata_path).read_text(encoding="utf-8"))
    records: list[CapabilityRecord] = []
    for tool in data.get("tools", []):
        records.append(
            CapabilityRecord(
                capability_id=f"{server_id}.{tool['name']}",
                name=tool.get("title", tool["name"]),
                version=str(tool.get("version", "unknown")),
                description=tool.get("description", ""),
                provider_type=ProviderType.MCP,
                source=server_id,
                supported_operations=[tool["name"]],
                trust_level=TrustLevel.EXPERIMENTAL,
                enabled=False,
                validation_status=ValidationStatus.UNTESTED,
                input_schema=tool.get("input_schema", {}),
                output_schema=tool.get("output_schema", {}),
                mcp_server_id=server_id,
                mcp_tool_name=tool["name"],
                risk_notes="MCP tool discovered from configured server metadata; disabled until tested, approved, and enabled.",
            )
        )
    return records


def _configured_server(server_id: str) -> dict[str, object] | None:
    path = CONFIG.mcp_servers_config_path
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    for server in data.get("servers", []):
        if server.get("id") == server_id and server.get("enabled", False):
            return server
    return None
