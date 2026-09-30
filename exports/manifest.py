from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from exports.models import ExportResult


def write_manifest(
    path: Path,
    *,
    source: dict[str, Any],
    engineering: dict[str, Any] | None,
    parameters: list[dict[str, Any]] | None,
    assembly: dict[str, Any] | None,
    results: list[ExportResult],
    generated_at: str,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "source": source,
        "generated_at": generated_at,
        "units": "mm",
        "formats": [
            {
                "format": result.format.value,
                "file": result.filename,
                "size_bytes": result.size_bytes,
                "checksum_sha256": result.checksum_sha256,
                "warnings": result.warnings,
                "metadata": result.metadata,
            }
            for result in results
            if result.format.value != "manifest"
        ],
        "engineering": engineering,
        "parameters": parameters or [],
        "assembly": assembly,
    }
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return path
