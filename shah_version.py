"""Single source of truth for the application version and build identity.

Every other module (API, CLI, launcher, About panel) reads from here so the
version is never duplicated. `web/package.json` keeps its own npm version for
tooling reasons; the value reported to users comes from this module.
"""

from __future__ import annotations

import subprocess
from functools import lru_cache
from pathlib import Path


APP_NAME = "SHAH INDUSTRIES"
APP_TAGLINE = "Local Engineering Workspace"
APP_VERSION = "0.19.0"

# Bumped when a persisted store layout changes in a way readers must know about.
SCHEMA_VERSION = "1"

SUPPORTED_PYTHON = (3, 11)
MIN_NODE_MAJOR = 20

_REPO_ROOT = Path(__file__).resolve().parent


@lru_cache(maxsize=1)
def build_commit() -> str | None:
    """Short git commit for this checkout, or None when git is unavailable.

    Git is a convenience here, never a runtime requirement: a packaged copy
    without a .git directory (or without git on PATH) simply reports no build.
    """
    if not (_REPO_ROOT / ".git").exists():
        return None
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    commit = result.stdout.strip()
    return commit or None


def version_line() -> str:
    """Human-readable one-liner, e.g. `SHAH INDUSTRIES 0.19.0 (build 4e90c94)`."""
    commit = build_commit()
    if commit:
        return f"{APP_NAME} {APP_VERSION} (build {commit})"
    return f"{APP_NAME} {APP_VERSION}"
