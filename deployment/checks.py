"""Environment diagnostics.

Every function here is read-only: `doctor` must never change system state. The
setup flow reuses these checks to decide what it needs to install, and does the
mutating separately in `bootstrap`.
"""

from __future__ import annotations

import importlib.metadata
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

from deployment import paths
from deployment.models import CheckResult, CheckStatus, DoctorReport
from deployment.ports import is_port_available
from shah_version import APP_VERSION, MIN_NODE_MAJOR, SUPPORTED_PYTHON, build_commit


def _ok(name: str, detail: str) -> CheckResult:
    return CheckResult(name=name, status=CheckStatus.PASS, detail=detail)


def _warn(name: str, detail: str, remedy: str | None = None) -> CheckResult:
    return CheckResult(name=name, status=CheckStatus.WARN, detail=detail, remedy=remedy)


def _fail(name: str, detail: str, remedy: str | None = None) -> CheckResult:
    return CheckResult(name=name, status=CheckStatus.FAIL, detail=detail, remedy=remedy)


def check_python_version() -> CheckResult:
    actual = sys.version_info
    label = f"{actual.major}.{actual.minor}.{actual.micro}"
    if (actual.major, actual.minor) == SUPPORTED_PYTHON:
        return _ok("Python", label)
    wanted = f"{SUPPORTED_PYTHON[0]}.{SUPPORTED_PYTHON[1]}"
    return _fail(
        "Python",
        f"{label} (expected {wanted}.x)",
        f"Create the supported environment with: py -{wanted} -m venv .venv311",
    )


def check_virtualenv() -> CheckResult:
    """A venv is strongly preferred but not fatal if dependencies resolve."""
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    if not in_venv:
        return _warn(
            "Virtual environment",
            "running against a system interpreter",
            "Activate the project environment: .\\.venv311\\Scripts\\Activate.ps1",
        )
    return _ok("Virtual environment", paths.relative(Path(sys.prefix)))


def _package_check(name: str, import_name: str | None = None) -> CheckResult:
    module = import_name or name
    try:
        __import__(module)
    except Exception as exc:  # noqa: BLE001 - any import problem is a failure here
        return _fail(
            name,
            f"import failed: {type(exc).__name__}",
            "Install dependencies: pip install -r requirements.txt",
        )
    try:
        return _ok(name, importlib.metadata.version(name))
    except importlib.metadata.PackageNotFoundError:
        return _ok(name, "installed")


def check_cadquery() -> CheckResult:
    """Import CadQuery and exercise OpenCascade with a trivial real solid."""
    try:
        import cadquery as cq
    except Exception as exc:  # noqa: BLE001
        return _fail(
            "CadQuery",
            f"import failed: {type(exc).__name__}",
            "Install dependencies: pip install -r requirements.txt",
        )
    try:
        solid = cq.Workplane("XY").box(1, 1, 1)
        volume = solid.val().Volume()
    except Exception as exc:  # noqa: BLE001
        return _fail(
            "OpenCascade geometry",
            f"kernel call failed: {type(exc).__name__}",
            "Reinstall CadQuery so its OpenCascade wheels match: pip install --force-reinstall cadquery",
        )
    if not 0.99 < volume < 1.01:
        return _fail("OpenCascade geometry", f"unit box volume was {volume:.4f}, expected 1.0")
    try:
        version = importlib.metadata.version("cadquery")
    except importlib.metadata.PackageNotFoundError:
        version = "installed"
    return _ok("CadQuery", f"{version} (OpenCascade geometry verified)")


def _run_tool(command: list[str]) -> tuple[bool, str]:
    """Run a version probe without a shell. Returns (ok, first output line)."""
    executable = shutil.which(command[0])
    if executable is None:
        return False, "not found on PATH"
    try:
        result = subprocess.run(
            [executable, *command[1:]],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"could not run: {type(exc).__name__}"
    if result.returncode != 0:
        return False, (result.stderr or result.stdout).strip().splitlines()[:1][0] if (result.stderr or result.stdout).strip() else "non-zero exit"
    output = (result.stdout or "").strip()
    return True, output.splitlines()[0] if output else ""


def check_node() -> CheckResult:
    ok, output = _run_tool(["node", "--version"])
    if not ok:
        return _fail(
            "Node.js",
            output,
            f"Install Node.js {MIN_NODE_MAJOR}+ LTS from https://nodejs.org and reopen the terminal",
        )
    label = output.lstrip("v")
    major_text = label.split(".", 1)[0]
    if not major_text.isdigit():
        return _warn("Node.js", f"unrecognized version {output!r}")
    major = int(major_text)
    if major < MIN_NODE_MAJOR:
        return _fail(
            "Node.js",
            f"{label} (need {MIN_NODE_MAJOR}+)",
            f"Install a current Node.js LTS ({MIN_NODE_MAJOR}+) from https://nodejs.org",
        )
    return _ok("Node.js", label)


def check_npm() -> CheckResult:
    # npm is a shim (npm.cmd) on Windows; shutil.which resolves it via PATHEXT.
    ok, output = _run_tool(["npm", "--version"])
    if not ok:
        return _fail("npm", output, "npm ships with Node.js; reinstall Node.js to restore it")
    return _ok("npm", output)


def check_frontend_dependencies() -> CheckResult:
    if not paths.WEB_PACKAGE_LOCK.exists():
        return _fail(
            "Frontend lockfile",
            "web/package-lock.json is missing",
            "Restore the lockfile from git; CI installs with npm ci and needs it",
        )
    if not paths.WEB_NODE_MODULES.exists():
        return _fail(
            "Frontend dependencies",
            "web/node_modules is missing",
            "Install them: cd web; npm.cmd ci",
        )
    # A node_modules that exists but lost its bin shims is a common half-install.
    if not (paths.WEB_NODE_MODULES / "vite").exists():
        return _warn(
            "Frontend dependencies",
            "web/node_modules looks incomplete (vite not present)",
            "Reinstall them: cd web; npm.cmd ci",
        )
    return _ok("Frontend dependencies", "installed")


def check_frontend_build() -> CheckResult:
    index = paths.WEB_DIST_DIR / "index.html"
    if not index.exists():
        return _warn(
            "Frontend build",
            "web/dist is not built",
            "Build it for production mode: python app.py build (dev mode does not need it)",
        )
    assets = paths.WEB_DIST_DIR / "assets"
    if not assets.is_dir() or not any(assets.iterdir()):
        return _warn(
            "Frontend build",
            "web/dist/index.html exists but assets are missing",
            "Rebuild: python app.py build",
        )
    return _ok("Frontend build", paths.relative(paths.WEB_DIST_DIR))


def check_writable(label: str, directory: Path) -> CheckResult:
    try:
        directory.mkdir(parents=True, exist_ok=True)
        probe = directory / ".shah_write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        return _fail(
            f"Writable {label}",
            f"{paths.relative(directory)} is not writable ({exc.strerror or exc})",
            "Check folder permissions, or move the repository somewhere writable",
        )
    return _ok(f"Writable {label}", paths.relative(directory))


def check_databases() -> CheckResult:
    """Confirm existing databases open. Missing files are fine on first run."""
    existing = [path for path in paths.DATABASE_FILES if path.exists()]
    if not existing:
        return _ok("Databases", "none yet (they initialize on first use)")
    unreadable: list[str] = []
    for path in existing:
        try:
            with sqlite3.connect(path) as conn:
                conn.execute("select count(*) from sqlite_master").fetchone()
        except sqlite3.Error as exc:
            unreadable.append(f"{path.name} ({exc})")
    if unreadable:
        return _fail(
            "Databases",
            "; ".join(unreadable),
            "Move the unreadable file aside to let it rebuild, or restore a backup. "
            "SHAH never deletes a database for you.",
        )
    return _ok("Databases", f"{len(existing)} readable")


def check_port(label: str, port: int, host: str = "127.0.0.1") -> CheckResult:
    if is_port_available(port, host):
        return _ok(f"{label} port {port}", "available")
    return _warn(
        f"{label} port {port}",
        "in use",
        "Another process holds it. Start on a different port, or stop that process.",
    )


def check_openai_key() -> CheckResult:
    """Absence is a warning: deterministic CAD does not need a key."""
    if os.getenv("OPENAI_API_KEY"):
        return _ok("OPENAI_API_KEY", "configured")
    return _warn(
        "OPENAI_API_KEY",
        "not configured - natural-language prompt parsing is unavailable",
        "Optional. Add OPENAI_API_KEY to .env to enable AI parsing. "
        "Manual CAD, projects, assemblies, exports, and evaluation work without it.",
    )


def check_env_file() -> CheckResult:
    if paths.ENV_PATH.exists():
        return _ok(".env", paths.relative(paths.ENV_PATH))
    return _warn(
        ".env",
        "not present",
        "Optional. Copy .env.example to .env to configure an OpenAI key.",
    )


def check_mcp_config() -> CheckResult:
    if paths.MCP_CONFIG_PATH.exists():
        return _ok("MCP config", paths.relative(paths.MCP_CONFIG_PATH))
    return _warn(
        "MCP config",
        "config/mcp_servers.json not present",
        "Optional. Only needed for capability invocation through MCP servers.",
    )


def run_doctor(
    *,
    backend_port: int = 8000,
    frontend_port: int = 5173,
    host: str = "127.0.0.1",
    include_ports: bool = True,
    include_frontend: bool = True,
) -> DoctorReport:
    """Collect every diagnostic without modifying system state.

    `include_frontend` is off for backend-only environments (CI jobs that never
    install npm packages), where a missing `node_modules` is expected rather
    than a problem to report.
    """
    results: list[CheckResult] = [
        check_python_version(),
        _ok("Python executable", sys.executable),
        check_virtualenv(),
        check_cadquery(),
        _package_check("pydantic"),
        _package_check("fastapi"),
        _package_check("uvicorn"),
        _package_check("openai"),
    ]
    if include_frontend:
        results += [
            check_node(),
            check_npm(),
            check_frontend_dependencies(),
            check_frontend_build(),
        ]
    results += [
        check_writable("outputs/", paths.OUTPUTS_DIR),
        check_writable("data/", paths.DATA_DIR),
        check_writable("runtime/", paths.RUNTIME_DIR),
        check_databases(),
        check_env_file(),
        check_openai_key(),
        check_mcp_config(),
    ]
    if include_ports:
        results.append(check_port("Backend", backend_port, host))
        results.append(check_port("Frontend", frontend_port, host))
    return DoctorReport(app_version=APP_VERSION, build=build_commit(), results=results)


def format_report(report: DoctorReport) -> str:
    """Render a doctor report as the aligned console block users see."""
    lines = [f"{'SHAH INDUSTRIES SYSTEM CHECK':<40}", ""]
    header = f"Version: {report.app_version}"
    if report.build:
        header += f"  Build: {report.build}"
    lines.append(header)
    lines.append("")
    for result in report.results:
        tag = f"[{result.status.value.upper()}]"
        lines.append(f"{tag:<7}{result.name}: {result.detail}")
        if result.remedy and result.status is not CheckStatus.PASS:
            for remedy_line in result.remedy.splitlines():
                lines.append(f"       {remedy_line}")
    lines.append("")
    if report.failures:
        lines.append("Core deterministic CAD is unavailable until the failures above are fixed.")
    elif report.warnings:
        lines.append("Core deterministic CAD remains available.")
    lines.append("")
    lines.append(f"Overall: {report.overall}")
    return "\n".join(lines)
