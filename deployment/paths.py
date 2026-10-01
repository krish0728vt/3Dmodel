"""Controlled filesystem locations for local deployment.

Every path the launcher creates, cleans, or archives is defined here and is
always resolved under the repository root. Nothing in this package accepts an
arbitrary user path for a destructive operation.
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = REPO_ROOT / "data"
OUTPUTS_DIR = REPO_ROOT / "outputs"
RUNTIME_DIR = REPO_ROOT / "runtime"
LOGS_DIR = RUNTIME_DIR / "logs"
BACKUPS_DIR = REPO_ROOT / "backups"

WEB_DIR = REPO_ROOT / "web"
WEB_DIST_DIR = WEB_DIR / "dist"
WEB_NODE_MODULES = WEB_DIR / "node_modules"
WEB_PACKAGE_LOCK = WEB_DIR / "package-lock.json"

CONFIG_DIR = REPO_ROOT / "config"
LOCAL_CONFIG_PATH = CONFIG_DIR / "local.json"
LOCAL_CONFIG_EXAMPLE_PATH = CONFIG_DIR / "local.example.json"
MCP_CONFIG_PATH = CONFIG_DIR / "mcp_servers.json"

ENV_PATH = REPO_ROOT / ".env"
ENV_EXAMPLE_PATH = REPO_ROOT / ".env.example"

VENV_DIR = REPO_ROOT / ".venv311"

PROCESS_STATE_PATH = RUNTIME_DIR / "shah_processes.json"
BACKEND_LOG = LOGS_DIR / "backend.log"
FRONTEND_LOG = LOGS_DIR / "frontend.log"
LAUNCHER_LOG = LOGS_DIR / "launcher.log"

# Directories the app needs in place before it can run.
REQUIRED_DIRS = (DATA_DIR, OUTPUTS_DIR, RUNTIME_DIR, LOGS_DIR)

# Databases the stores manage. Used for reporting and backups, never deleted.
DATABASE_FILES = (
    DATA_DIR / "shah_learning.db",
    DATA_DIR / "shah_projects.db",
    DATA_DIR / "shah_assemblies.db",
    DATA_DIR / "shah_exports.db",
)


def ensure_runtime_dirs() -> list[Path]:
    """Create the required directories if missing. Returns the ones created."""
    created: list[Path] = []
    for directory in REQUIRED_DIRS:
        if not directory.exists():
            directory.mkdir(parents=True, exist_ok=True)
            created.append(directory)
    return created


def relative(path: Path) -> str:
    """Repo-relative POSIX string for display, falling back to the full path."""
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)
