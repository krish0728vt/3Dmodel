from __future__ import annotations

import re
from pathlib import Path


_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")


class UnsafeExportPathError(ValueError):
    """Raised when an export path or filename escapes the controlled output tree."""


def safe_stem(name: str, fallback: str = "export") -> str:
    cleaned = _SAFE_RE.sub("_", name.strip()).strip("._-")
    if not cleaned:
        cleaned = fallback
    if cleaned in {".", ".."}:
        cleaned = fallback
    return cleaned[:96]


def revision_filename(name: str, revision: int, suffix: str) -> str:
    suffix = suffix if suffix.startswith(".") else f".{suffix}"
    return f"{safe_stem(name)}_rev_{revision:03d}{suffix.lower()}"


def controlled_output_dir(source_id: str, revision: int) -> Path:
    return Path("outputs") / "exports" / safe_stem(source_id, "source") / f"rev_{revision:03d}"


def ensure_controlled_path(path: Path, root: Path = Path("outputs")) -> Path:
    resolved_path = path.resolve()
    resolved_root = root.resolve()
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise UnsafeExportPathError(f"Export path escapes controlled output directory: {path}") from exc
    if ".." in path.parts:
        raise UnsafeExportPathError(f"Export path contains parent traversal: {path}")
    return path
