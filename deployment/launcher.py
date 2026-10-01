"""Startup orchestration for development and local production modes.

Development mode runs uvicorn --reload plus the Vite dev server (two ports).
Production mode builds the frontend and serves it from FastAPI, so a single
origin serves both the app and the API.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import time
import webbrowser
import zipfile
from datetime import datetime
from pathlib import Path

from deployment import checks, paths
from deployment.health import wait_for_backend, wait_for_frontend
from deployment.models import (
    CheckStatus,
    LaunchMode,
    LocalConfig,
    ProcessRecord,
)
from deployment.ports import PortUnavailableError, resolve_port
from deployment.processes import (
    IS_WINDOWS,
    LaunchError,
    backend_command,
    build_state,
    clear_state,
    frontend_command,
    is_tracked_process_valid,
    open_log,
    read_state,
    start_process,
    stop_process,
    terminate_popen,
    write_state,
)
from shah_version import APP_TAGLINE, APP_NAME, APP_VERSION, build_commit


def load_local_config() -> LocalConfig:
    """Read `config/local.json` when present, else defaults.

    An unreadable or invalid file is reported and ignored rather than being
    treated as fatal, so a bad edit never blocks startup.
    """
    if not paths.LOCAL_CONFIG_PATH.exists():
        return LocalConfig()
    try:
        raw = json.loads(paths.LOCAL_CONFIG_PATH.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            # `_`-prefixed keys are comments (the example file ships one), so they
            # are dropped before validation. Any other unknown key is still an
            # error, which catches typos in real setting names.
            raw = {key: value for key, value in raw.items() if not key.startswith("_")}
        return LocalConfig.model_validate(raw)
    except (OSError, ValueError) as exc:
        print(f"WARNING: ignoring {paths.relative(paths.LOCAL_CONFIG_PATH)}: {exc}")
        return LocalConfig()


def _preflight(*, dev: bool) -> int:
    """Block startup only on things that genuinely prevent running."""
    required = [
        checks.check_python_version(),
        checks.check_cadquery(),
        checks.check_writable("data/", paths.DATA_DIR),
        checks.check_writable("outputs/", paths.OUTPUTS_DIR),
        checks.check_writable("runtime/", paths.RUNTIME_DIR),
        checks.check_databases(),
    ]
    if dev:
        required += [checks.check_node(), checks.check_npm(), checks.check_frontend_dependencies()]

    failures = [result for result in required if result.status is CheckStatus.FAIL]
    if failures:
        print("Cannot start. The following must be fixed first:")
        print()
        for failure in failures:
            print(f"  [FAIL] {failure.name}: {failure.detail}")
            if failure.remedy:
                for line in failure.remedy.splitlines():
                    print(f"         {line}")
        print()
        print("Run `python app.py doctor` for the full picture.")
        return 1
    return 0


def _enable_line_buffering() -> None:
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except (AttributeError, OSError, ValueError):
        pass


def _print_banner() -> None:
    commit = build_commit()
    print(APP_NAME)
    print(APP_TAGLINE)
    print()
    suffix = f"  Build: {commit}" if commit else ""
    print(f"Version: {APP_VERSION}{suffix}")
    print(f"Python: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")


def _warn_if_public(host: str) -> None:
    if host in {"127.0.0.1", "localhost", "::1"}:
        return
    print()
    print("WARNING: binding to a non-local address.")
    print(f"  Host {host} may be reachable from your network.")
    print("  SHAH is designed for local single-user use and has no authentication,")
    print("  authorization, rate limiting, or request auditing. Do not expose it")
    print("  to an untrusted network or the internet.")
    print()


def serve(
    *,
    dev: bool = False,
    host: str | None = None,
    backend_port: int | None = None,
    frontend_port: int | None = None,
    open_browser: bool | None = None,
    auto_port: bool = False,
    build: bool = False,
    timeout: int | None = None,
) -> int:
    """Start the workspace and block until interrupted. Returns an exit code."""
    config = load_local_config()
    host = host or config.backend_host
    backend_port = backend_port or config.backend_port
    frontend_port = frontend_port or config.frontend_port
    startup_timeout = timeout or config.startup_timeout
    should_open = config.open_browser if open_browser is None else open_browser

    if _preflight(dev=dev) != 0:
        return 1

    paths.ensure_runtime_dirs()

    # A previous session still running would fight us for the ports.
    existing = read_state()
    if existing is not None:
        live = [r for r in existing.processes if is_tracked_process_valid(r)]
        if live:
            print("A SHAH session is already running:")
            for record in live:
                print(f"  {record.name}: PID {record.pid} on port {record.port}")
            print()
            print("Stop it first with: python app.py stop")
            return 1
        clear_state()

    try:
        backend_port = resolve_port(
            backend_port, host=host, flag="--backend-port", auto=auto_port
        )
        if dev:
            frontend_port = resolve_port(
                frontend_port, host=host, flag="--frontend-port", auto=auto_port
            )
    except PortUnavailableError as exc:
        print("ERROR:")
        print(str(exc))
        return 1

    if not dev:
        if build:
            print("Building the frontend before starting...")
            if run_build(run_tests=False) != 0:
                return 1
        elif not (paths.WEB_DIST_DIR / "index.html").is_file():
            print("Cannot start production mode: the frontend is not built.")
            print()
            print("  Build it first:   python app.py build")
            print("  Or build and run: python app.py serve --production --build")
            print("  Or use dev mode:  python app.py serve --dev")
            return 1

    _warn_if_public(host)
    return _run_session(
        dev=dev,
        host=host,
        backend_port=backend_port,
        frontend_port=frontend_port,
        startup_timeout=startup_timeout,
        should_open=should_open,
    )


def _run_session(
    *,
    dev: bool,
    host: str,
    backend_port: int,
    frontend_port: int,
    startup_timeout: int,
    should_open: bool,
) -> int:
    mode = LaunchMode.DEV if dev else LaunchMode.PRODUCTION
    api_url = f"http://{host}:{backend_port}"
    web_url = f"http://{host}:{frontend_port}" if dev else api_url

    backend_env_note = ""
    if not dev:
        # Tell the FastAPI app to mount web/dist for this child process only.
        os.environ["SHAH_SERVE_FRONTEND"] = "1"
        backend_env_note = " (also serving web/dist)"

    processes: list[tuple[str, subprocess.Popen[bytes]]] = []
    logs: list[object] = []
    records: list[ProcessRecord] = []

    # Python block-buffers stdout when it is a pipe rather than a terminal, which
    # would hide the status block and the URLs from anyone redirecting output to
    # a file. Child processes write straight to the same handle, so unflushed
    # launcher text would also appear out of order.
    _enable_line_buffering()

    _print_banner()
    print(f"Mode: {mode.value}")
    print()

    try:
        backend_log = open_log(paths.BACKEND_LOG)
        logs.append(backend_log)
        b_command = backend_command(host=host, port=backend_port, reload=dev)
        print(f"Starting backend on port {backend_port}{backend_env_note}...")
        backend = start_process(
            name="backend", command=b_command, cwd=paths.REPO_ROOT, log_file=backend_log
        )
        processes.append(("backend", backend))
        records.append(
            ProcessRecord(
                name="backend",
                pid=backend.pid,
                port=backend_port,
                command=b_command,
                log_path=paths.relative(paths.BACKEND_LOG),
            )
        )

        health = wait_for_backend(
            api_url, timeout=startup_timeout, is_alive=lambda: backend.poll() is None
        )
        if health is None:
            return _startup_failure("backend", backend, paths.BACKEND_LOG, processes, logs)

        if dev:
            frontend_log = open_log(paths.FRONTEND_LOG)
            logs.append(frontend_log)
            f_command = frontend_command(host=host, port=frontend_port)
            print(f"Starting frontend dev server on port {frontend_port}...")
            frontend = start_process(
                name="frontend",
                command=f_command,
                cwd=paths.WEB_DIR,
                log_file=frontend_log,
                # Point Vite's /api proxy at the backend we just started, which
                # may not be on the default port.
                env={"SHAH_API_PROXY": api_url},
            )
            processes.append(("frontend", frontend))
            records.append(
                ProcessRecord(
                    name="frontend",
                    pid=frontend.pid,
                    port=frontend_port,
                    command=f_command,
                    log_path=paths.relative(paths.FRONTEND_LOG),
                )
            )
            if not wait_for_frontend(
                web_url, timeout=startup_timeout, is_alive=lambda: frontend.poll() is None
            ):
                return _startup_failure("frontend", frontend, paths.FRONTEND_LOG, processes, logs)

        write_state(build_state(mode=mode, host=host, records=records))

        print()
        print("Backend: ONLINE")
        print(f"Frontend: {'ONLINE' if dev else 'ONLINE (served by backend)'}")
        print(f"API: {api_url}/api/health")
        print(f"Web: {web_url}")
        if not os.getenv("OPENAI_API_KEY"):
            print()
            print("AI NOT CONFIGURED - natural-language prompts are unavailable.")
            print("  Manual CAD, projects, assemblies, exports, and evaluation work normally.")
        print()
        print(f"Logs: {paths.relative(paths.LOGS_DIR)}/")
        print()
        print("Press Ctrl+C to stop.")

        if should_open:
            webbrowser.open(web_url)

        return _wait_until_interrupted(processes)
    except LaunchError as exc:
        print()
        print("STARTUP FAILED")
        print(str(exc))
        _shutdown(processes, logs)
        return 1
    finally:
        _shutdown(processes, logs)
        clear_state()


def _startup_failure(
    name: str,
    process: subprocess.Popen[bytes],
    log_path: Path,
    processes: list[tuple[str, subprocess.Popen[bytes]]],
    logs: list[object],
) -> int:
    """Report why a child never became healthy, then clean up."""
    print()
    print(f"STARTUP FAILED: the {name} did not become healthy in time.")
    exit_code = process.poll()
    if exit_code is not None:
        print(f"  The {name} process exited with code {exit_code}.")
    else:
        print(f"  The {name} process is running but never answered a health check.")
    # Flush so the tail we print includes everything written so far.
    for handle in logs:
        try:
            handle.flush()  # type: ignore[attr-defined]
        except (OSError, ValueError):
            pass
    tail = _log_tail(log_path)
    if tail:
        print()
        print(f"  Last lines of {paths.relative(log_path)}:")
        for line in tail:
            print(f"    {line}")
    print()
    print("  Common causes: a port taken after the check, a missing dependency,")
    print("  or an unreadable database. Run `python app.py doctor` for details.")
    return 1


def _log_tail(path: Path, lines: int = 15) -> list[str]:
    try:
        content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    return [_console_safe(line.rstrip()) for line in content[-lines:] if line.strip()]


def _console_safe(text: str) -> str:
    """Drop characters the active console encoding cannot represent.

    Vite and npm emit arrows and box-drawing glyphs. On a cp1252 Windows console
    printing those raises UnicodeEncodeError, which would crash the handler that
    is trying to report a startup failure.
    """
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        return text.encode(encoding, errors="replace").decode(encoding, errors="replace")
    except (LookupError, UnicodeError):
        return text.encode("ascii", errors="replace").decode("ascii")


def _wait_until_interrupted(
    processes: list[tuple[str, subprocess.Popen[bytes]]],
) -> int:
    """Block until Ctrl+C, or until a child exits on its own."""
    try:
        while True:
            for name, process in processes:
                code = process.poll()
                if code is not None:
                    print()
                    print(f"The {name} process exited unexpectedly with code {code}.")
                    print(f"  See {paths.relative(paths.LOGS_DIR)}/ for details.")
                    return 1
            time.sleep(0.5)
    except KeyboardInterrupt:
        print()
        print("Shutting down...")
        return 0


def _shutdown(
    processes: list[tuple[str, subprocess.Popen[bytes]]],
    logs: list[object],
) -> None:
    """Terminate children (deepest first) and close log handles. Idempotent."""
    for name, process in reversed(processes):
        if process.poll() is None:
            terminate_popen(process)
            print(f"  stopped {name}")
    processes.clear()
    for handle in logs:
        try:
            handle.close()  # type: ignore[attr-defined]
        except (OSError, ValueError):
            pass
    logs.clear()


def stop() -> int:
    """Stop only the processes this launcher recorded."""
    state = read_state()
    if state is None:
        print("No SHAH session is recorded as running.")
        print(f"  (no {paths.relative(paths.PROCESS_STATE_PATH)})")
        return 0

    print(f"Stopping the {state.mode.value} session started at {state.started_at}...")
    any_stopped = False
    # Reverse order (frontend before backend) mirrors the launcher's own
    # shutdown. Stopping the backend first would make a still-running launcher
    # notice the exit and tear down the frontend concurrently, racing us.
    for record in reversed(state.processes):
        outcome = stop_process(record)
        if outcome == "stopped":
            print(f"  {record.name} (PID {record.pid}): stopped")
            any_stopped = True
        elif outcome == "already-exited":
            print(f"  {record.name} (PID {record.pid}): already exited")
        else:
            print(
                f"  {record.name} (PID {record.pid}): stale entry - that PID no longer "
                f"belongs to a SHAH process, so it was left alone"
            )
    clear_state()
    if not any_stopped:
        print("Nothing was running; cleared the stale state file.")
    return 0


def status() -> int:
    """Report recorded processes and live API health."""
    state = read_state()
    print(f"{APP_NAME} {APP_VERSION}")
    commit = build_commit()
    if commit:
        print(f"Build: {commit}")
    print()
    if state is None:
        print("Backend: OFFLINE")
        print("Frontend: OFFLINE")
        print()
        print("No session is recorded. Start one with: .\\scripts\\start.ps1")
        return 0

    print(f"Mode: {state.mode.value}")
    print(f"Started: {state.started_at}")
    print()

    backend = state.process("backend")
    for name in ("backend", "frontend"):
        record = state.process(name)
        label = name.capitalize()
        if record is None:
            if name == "frontend" and state.mode is LaunchMode.PRODUCTION:
                print(f"{label}: served by backend")
            else:
                print(f"{label}: not started")
            continue
        alive = is_tracked_process_valid(record)
        print(f"{label}: {'ONLINE' if alive else 'STALE (recorded PID is not running)'}")
        print(f"  PID {record.pid}")
        print(f"  Port {record.port}")
        if record.log_path:
            print(f"  Log {record.log_path}")

    print()
    if backend is not None:
        from deployment.health import probe_json

        payload = probe_json(f"http://{state.host}:{backend.port}/api/health")
        if payload is not None and payload.get("status") == "online":
            print(f"API health: PASS ({payload.get('route_count', '?')} routes)")
        else:
            print("API health: FAIL (no response)")
            return 1
    return 0


def run_build(*, run_tests: bool = False, run_typecheck: bool = True) -> int:
    """Typecheck, optionally test, then build the frontend and verify output."""
    npm = "npm.cmd" if IS_WINDOWS else "npm"
    node_check = checks.check_frontend_dependencies()
    if node_check.status is CheckStatus.FAIL:
        print(f"Cannot build: {node_check.detail}")
        if node_check.remedy:
            print(f"  {node_check.remedy}")
        return 1

    steps: list[tuple[str, list[str]]] = []
    if run_typecheck:
        steps.append(("Frontend typecheck", [npm, "run", "typecheck"]))
    if run_tests:
        steps.append(("Frontend tests", [npm, "test"]))
    steps.append(("Frontend build", [npm, "run", "build"]))

    for label, command in steps:
        print(f"==> {label}")
        executable = shutil.which(command[0])
        if executable is None:
            print(f"  {command[0]!r} was not found on PATH.")
            return 1
        result = subprocess.run(  # noqa: S603 - explicit arg list, shell never used
            [executable, *command[1:]], cwd=str(paths.WEB_DIR), check=False
        )
        if result.returncode != 0:
            print(f"FAIL: {label} exited with {result.returncode}")
            return 1

    index = paths.WEB_DIST_DIR / "index.html"
    assets = paths.WEB_DIST_DIR / "assets"
    if not index.is_file():
        print("FAIL: the build finished but web/dist/index.html is missing.")
        return 1
    if not assets.is_dir() or not any(assets.iterdir()):
        print("FAIL: the build finished but web/dist/assets is empty.")
        return 1
    print()
    print(f"Build verified: {paths.relative(paths.WEB_DIST_DIR)}")
    return 0


# Locations `clean` is allowed to remove. Everything here is regenerated by a
# build or a benchmark run; user data is deliberately absent.
_CLEANABLE = (
    ("frontend build", paths.WEB_DIST_DIR),
    ("evaluation work", paths.OUTPUTS_DIR / "evaluation" / "work"),
    ("runtime logs", paths.LOGS_DIR),
)


def clean(*, yes: bool = False) -> int:
    """Remove only regenerable artifacts. Never touches databases or exports."""
    present = [(label, path) for label, path in _CLEANABLE if path.exists()]
    print("Clean removes only regenerable artifacts:")
    for label, path in _CLEANABLE:
        marker = "" if path.exists() else "  (not present)"
        print(f"  - {label}: {paths.relative(path)}{marker}")
    print()
    print("It never removes data/ databases, outputs/ exports, or user projects.")
    print()
    if not present:
        print("Nothing to clean.")
        return 0
    if not yes:
        print("Re-run with --yes to proceed.")
        return 0

    state = read_state()
    if state is not None and any(is_tracked_process_valid(r) for r in state.processes):
        print("A session is running. Stop it first: python app.py stop")
        return 1

    for label, path in present:
        shutil.rmtree(path, ignore_errors=True)
        print(f"  removed {paths.relative(path)}")
    return 0


def backup() -> int:
    """Archive local databases and non-secret config into backups/.

    Uses an explicit allow-list. `.env`, node_modules, the virtualenv, and logs
    are never included.
    """
    paths.BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_path = paths.BACKUPS_DIR / f"shah_backup_{stamp}.zip"

    members: list[Path] = [path for path in paths.DATABASE_FILES if path.is_file()]
    capabilities_registry = paths.DATA_DIR / "capabilities.json"
    if capabilities_registry.is_file():
        members.append(capabilities_registry)
    if paths.MCP_CONFIG_PATH.is_file():
        members.append(paths.MCP_CONFIG_PATH)
    if paths.LOCAL_CONFIG_PATH.is_file():
        members.append(paths.LOCAL_CONFIG_PATH)

    if not members:
        print("Nothing to back up yet: no databases or local config exist.")
        return 0

    print(f"Creating {paths.relative(archive_path)}")
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for member in members:
            arcname = paths.relative(member)
            archive.write(member, arcname=arcname)
            print(f"  + {arcname}")
    print()
    print("Excluded by design: .env, secrets, node_modules, .venv311, runtime logs.")
    size_kb = archive_path.stat().st_size / 1024
    print(f"Backup complete ({size_kb:.1f} KB).")
    return 0


def _install_sigterm_handler() -> None:
    """Treat SIGTERM like Ctrl+C so shutdown still runs under a task runner."""
    def _handler(signum: int, frame: object) -> None:  # noqa: ARG001
        raise KeyboardInterrupt

    try:
        signal.signal(signal.SIGTERM, _handler)
    except (ValueError, OSError, AttributeError):
        pass
