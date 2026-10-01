"""Local deployment: environment checks, setup, process orchestration, packaging.

Entry points are exposed through the `app.py` CLI (`serve`, `setup`, `doctor`,
`stop`, `status`, `build`, `clean`, `backup`, `version`) and the PowerShell
wrappers in `scripts/`.
"""

from __future__ import annotations

__all__ = [
    "bootstrap",
    "checks",
    "health",
    "launcher",
    "models",
    "paths",
    "ports",
    "processes",
]
