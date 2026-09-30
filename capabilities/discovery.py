from __future__ import annotations

from pathlib import Path

from capabilities.models import CapabilityManifest


def inspect_manifest(path: str | Path) -> CapabilityManifest:
    """Validate a local capability manifest without installing or executing anything."""

    return CapabilityManifest.model_validate_json(Path(path).read_text(encoding="utf-8"))
