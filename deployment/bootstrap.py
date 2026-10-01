"""First-run setup.

Unlike `checks`, this module is allowed to change state -- but only ever by
creating directories, copying `.env.example`, or installing declared
dependencies into the project virtual environment. It never touches global
Python packages, never overwrites an existing `.env`, and never deletes
`node_modules` unless explicitly asked to repair.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from deployment import checks, paths
from deployment.processes import IS_WINDOWS


class SetupError(RuntimeError):
    """A setup problem with a message already written for the user."""


def _run(command: list[str], *, cwd: Path, label: str) -> None:
    """Run an install command with no shell, streaming output to the console."""
    executable = shutil.which(command[0])
    if executable is None:
        raise SetupError(f"{label} failed: {command[0]!r} was not found on PATH.")
    print(f"  $ {' '.join(command)}")
    try:
        result = subprocess.run(  # noqa: S603 - explicit arg list, shell never used
            [executable, *command[1:]],
            cwd=str(cwd),
            check=False,
        )
    except OSError as exc:
        raise SetupError(f"{label} failed: {exc}") from exc
    if result.returncode != 0:
        raise SetupError(f"{label} failed with exit code {result.returncode}.")


def ensure_directories() -> list[Path]:
    created = paths.ensure_runtime_dirs()
    for directory in created:
        print(f"  created {paths.relative(directory)}/")
    if not created:
        print("  runtime directories already present")
    return created


def ensure_env_file() -> str:
    """Copy `.env.example` to `.env` when absent. Never overwrites."""
    if paths.ENV_PATH.exists():
        return "already present"
    if not paths.ENV_EXAMPLE_PATH.exists():
        return "skipped (.env.example missing)"
    shutil.copyfile(paths.ENV_EXAMPLE_PATH, paths.ENV_PATH)
    return "created from .env.example"


def install_python_dependencies(*, include_dev: bool = True) -> str:
    """Install requirements into the *current* interpreter's environment.

    Refuses to run outside a virtual environment so a global site-packages is
    never modified.
    """
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    if not in_venv:
        raise SetupError(
            "Refusing to install packages into a system Python.\n"
            "  Activate the project environment first:\n"
            "    .\\.venv311\\Scripts\\Activate.ps1\n"
            "  or run setup through scripts/setup.ps1, which does it for you."
        )
    command = [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"]
    if include_dev and (paths.REPO_ROOT / "requirements-dev.txt").exists():
        command += ["-r", "requirements-dev.txt"]
    _run(command, cwd=paths.REPO_ROOT, label="Installing Python dependencies")
    return "installed"


def install_frontend_dependencies(*, repair: bool = False) -> str:
    """Install npm dependencies, preferring `npm ci` for a locked install.

    Windows frequently fails `npm ci` with EPERM because a running Vite process
    or an editor holds a Rollup native binary open. That is a file lock, not a
    broken lockfile, so we explain it rather than deleting node_modules -- which
    is only done when the caller explicitly asks to repair.
    """
    npm = "npm.cmd" if IS_WINDOWS else "npm"
    if not paths.WEB_PACKAGE_LOCK.exists():
        raise SetupError(
            "web/package-lock.json is missing, so a reproducible install is not possible.\n"
            "  Restore it from git before running setup."
        )
    if repair:
        if paths.WEB_NODE_MODULES.exists():
            print(f"  removing {paths.relative(paths.WEB_NODE_MODULES)}/ (repair requested)")
            shutil.rmtree(paths.WEB_NODE_MODULES, ignore_errors=True)

    try:
        _run([npm, "ci"], cwd=paths.WEB_DIR, label="Installing frontend dependencies")
        return "installed via npm ci"
    except SetupError as exc:
        print()
        print("  npm ci did not succeed.")
        print(_NPM_EPERM_GUIDANCE)
        if paths.WEB_NODE_MODULES.exists():
            # The lockfile is present and valid, so a non-destructive install is
            # a reasonable fallback; it reconciles without wiping the tree.
            print("  Falling back to `npm install` against the existing lockfile.")
            _run([npm, "install"], cwd=paths.WEB_DIR, label="Installing frontend dependencies")
            return "installed via npm install (npm ci was blocked)"
        raise exc


_NPM_EPERM_GUIDANCE = """
  On Windows this is usually a file lock (EPERM / unlink on a Rollup .node
  binary), not a lockfile problem. To clear it:
    1. Stop any running dev server (python app.py stop).
    2. Close editors or terminals holding files under web/node_modules.
    3. Pause antivirus scanning of the repository if it locks binaries.
    4. Run setup again.
  If it still fails, repair the tree explicitly:
    python app.py setup --repair-frontend
""".rstrip()


def initialize_databases() -> list[str]:
    """Open each store once so a fresh checkout gets its schema created.

    Existing databases are opened, never recreated: the stores apply their own
    schema on connect, and a genuinely incompatible file surfaces as a clean
    error rather than being destroyed.
    """
    created: list[str] = []
    paths.DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        from assemblies.store import AssemblyStore
        from exports.store import ExportStore
        from learning.store import LearningStore
        from projects.store import ProjectStore
    except ImportError as exc:
        raise SetupError(f"Could not load the data stores: {exc}") from exc

    for label, factory in (
        ("learning", LearningStore),
        ("projects", ProjectStore),
        ("assemblies", AssemblyStore),
        ("exports", ExportStore),
    ):
        try:
            factory()
        except Exception as exc:  # noqa: BLE001 - report which store, keep going
            raise SetupError(
                f"The {label} database could not be initialized: {exc}\n"
                f"  Move the file aside to let it rebuild, or restore a backup.\n"
                f"  SHAH never deletes a database for you."
            ) from exc
        created.append(label)
    return created


def run_setup(
    *,
    install_python: bool = True,
    install_frontend: bool = True,
    repair_frontend: bool = False,
) -> int:
    """Guided, idempotent first-run setup. Returns a process exit code."""
    print("SHAH INDUSTRIES SETUP")
    print()
    print("This will:")
    print("  - create data/, outputs/, runtime/, runtime/logs/ if missing")
    print("  - create .env from .env.example if missing (never overwritten)")
    if install_python:
        print("  - install Python dependencies into the active virtual environment")
    if install_frontend:
        verb = "reinstall (repair)" if repair_frontend else "install"
        print(f"  - {verb} frontend dependencies with npm")
    print("  - initialize the local databases without touching existing data")
    print()

    try:
        print("Directories:")
        ensure_directories()
        print()

        print(f"Environment file: {ensure_env_file()}")
        print()

        if install_python:
            print("Python dependencies:")
            install_python_dependencies()
            print()

        if install_frontend:
            print("Frontend dependencies:")
            print(f"  {install_frontend_dependencies(repair=repair_frontend)}")
            print()

        print("Databases:")
        for label in initialize_databases():
            print(f"  {label}: ready")
        print()
    except SetupError as exc:
        print()
        print("SETUP FAILED")
        print(str(exc))
        return 1

    report = checks.run_doctor(include_ports=False)
    print(checks.format_report(report))
    print()
    if report.failures:
        print("Setup finished, but the checks above must be resolved before starting.")
        return 1
    print("Setup complete. Start the workspace with: .\\scripts\\start.ps1")
    return 0


