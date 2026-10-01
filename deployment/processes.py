"""Child process orchestration and the launcher state file.

Safety rules this module enforces:

* `shell=True` is never used; every command is an explicit argument list.
* Only PIDs recorded in `runtime/shah_processes.json` are ever signalled.
* A recorded PID is re-validated (running, and image name still plausible)
  before it is signalled, so a stale file cannot hit a recycled PID.
* On Windows the whole child tree is terminated via `taskkill /T` against our
  own tracked PID, because `npm.cmd` shims would otherwise orphan `node.exe`.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from deployment import paths
from deployment.models import LaunchMode, LaunchState, ProcessRecord
from shah_version import APP_VERSION


IS_WINDOWS = os.name == "nt"

# Image names we accept for each tracked process, as a guard against PID reuse.
_EXPECTED_IMAGES = {
    "backend": ("python.exe", "python", "python3", "python3.11", "pythonw.exe"),
    "frontend": ("node.exe", "node", "cmd.exe", "npm.cmd", "sh", "bash"),
}


class LaunchError(RuntimeError):
    """A startup problem with a message already written for the user."""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def open_log(path: Path) -> object:
    """Open a per-session log file, truncating the previous session's contents.

    Truncate-per-session keeps logs bounded without a rotation policy, which is
    more than enough for a local launcher.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    return path.open("w", encoding="utf-8", errors="replace")


def start_process(
    *,
    name: str,
    command: list[str],
    cwd: Path,
    log_file: object | None,
    env: dict[str, str] | None = None,
) -> subprocess.Popen[bytes]:
    """Spawn a child process with no shell, streaming output to `log_file`.

    On Windows the child gets its own process group so a console Ctrl+C aimed at
    the launcher does not race us to the children; we stop them explicitly.

    `env` is overlaid on the current environment rather than replacing it, so the
    child keeps PATH and the rest of the inherited context.
    """
    if not command:
        raise LaunchError(f"No command supplied for {name}.")
    executable = shutil.which(command[0])
    if executable is None:
        raise LaunchError(
            f"Cannot start {name}: {command[0]!r} was not found on PATH.\n"
            f"  Run `python app.py doctor` to see what is missing."
        )
    creation_flags = 0
    if IS_WINDOWS:
        creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP
    stdout = log_file if log_file is not None else None
    child_env = None
    if env:
        child_env = {**os.environ, **env}
    try:
        return subprocess.Popen(  # noqa: S603 - explicit arg list, shell never used
            [executable, *command[1:]],
            cwd=str(cwd),
            stdout=stdout,
            stderr=subprocess.STDOUT if stdout is not None else None,
            stdin=subprocess.DEVNULL,
            creationflags=creation_flags,
            close_fds=True,
            env=child_env,
        )
    except OSError as exc:
        raise LaunchError(f"Cannot start {name}: {exc}") from exc


def pid_is_running(pid: int) -> bool:
    """True when a process with `pid` currently exists."""
    if pid <= 0:
        return False
    if IS_WINDOWS:
        return _windows_image_name(pid) is not None
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Exists but is owned by someone else, so it is not ours to stop.
        return True
    return True


def _windows_image_name(pid: int) -> str | None:
    """Image name for `pid` via tasklist, or None when no such process exists."""
    tasklist = shutil.which("tasklist")
    if tasklist is None:
        return None
    try:
        result = subprocess.run(  # noqa: S603 - fixed binary, explicit args
            [tasklist, "/FI", f"PID eq {pid}", "/NH", "/FO", "CSV"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    line = result.stdout.strip()
    if not line or "No tasks" in line:
        return None
    # CSV form: "image.exe","1234","Console","1","12,345 K"
    first = line.splitlines()[0]
    if not first.startswith('"'):
        return None
    return first.split('","', 1)[0].strip('"')


def is_tracked_process_valid(record: ProcessRecord) -> bool:
    """True when `record`'s PID is alive and still looks like the right program.

    The image-name guard is best-effort: on Windows we can read it cheaply, and
    elsewhere liveness is all we check. It exists to stop a stale state file from
    signalling an unrelated process that inherited the PID.
    """
    if not pid_is_running(record.pid):
        return False
    if not IS_WINDOWS:
        return True
    image = _windows_image_name(record.pid)
    if image is None:
        return False
    expected = _EXPECTED_IMAGES.get(record.name, ())
    return image.lower() in {candidate.lower() for candidate in expected}


def stop_process(record: ProcessRecord, *, timeout: float = 10.0) -> str:
    """Stop one tracked process. Returns a short outcome word for reporting.

    Outcomes: "stopped", "already-exited", or "stale" when the PID no longer
    belongs to one of our programs.
    """
    if not pid_is_running(record.pid):
        return "already-exited"
    if not is_tracked_process_valid(record):
        # Either the PID was recycled by an unrelated program, or our own
        # process is exiting right now and its image can no longer be read.
        # Re-check liveness so a shutting-down child is not misreported as a
        # stale entry; if it is genuinely gone, say so.
        if not pid_is_running(record.pid):
            return "already-exited"
        # Still alive and not ours. Leave it strictly alone.
        return "stale"
    if IS_WINDOWS:
        return _windows_kill_tree(record.pid, timeout=timeout)
    return _posix_stop(record.pid, timeout=timeout)


def _windows_kill_tree(pid: int, *, timeout: float) -> str:
    """Terminate a process and its descendants with taskkill /T.

    npm.cmd spawns node as a grandchild, so killing only our direct child would
    leave an orphaned Vite server holding the port.
    """
    taskkill = shutil.which("taskkill")
    if taskkill is None:
        return "stale"
    try:
        subprocess.run(  # noqa: S603 - fixed binary, explicit args, our own PID
            [taskkill, "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "stale"
    return "stopped" if not pid_is_running(pid) else "stale"


def _posix_stop(pid: int, *, timeout: float) -> str:
    import signal
    import time

    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            os.kill(pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            return "already-exited"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not pid_is_running(pid):
            return "stopped"
        time.sleep(0.2)
    try:
        os.kill(pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    return "stopped" if not pid_is_running(pid) else "stale"


def terminate_popen(process: subprocess.Popen[bytes], *, timeout: float = 10.0) -> None:
    """Best-effort shutdown of a live Popen handle, including its tree."""
    if process.poll() is not None:
        return
    if IS_WINDOWS:
        _windows_kill_tree(process.pid, timeout=timeout)
    else:
        try:
            process.terminate()
        except OSError:
            pass
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            process.kill()
        except OSError:
            pass


def write_state(state: LaunchState) -> Path:
    paths.RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    paths.PROCESS_STATE_PATH.write_text(state.model_dump_json(indent=2), encoding="utf-8")
    return paths.PROCESS_STATE_PATH


def read_state() -> LaunchState | None:
    """Load the state file, returning None when absent or unreadable."""
    if not paths.PROCESS_STATE_PATH.exists():
        return None
    try:
        return LaunchState.model_validate_json(
            paths.PROCESS_STATE_PATH.read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return None


def clear_state() -> None:
    paths.PROCESS_STATE_PATH.unlink(missing_ok=True)


def build_state(
    *,
    mode: LaunchMode,
    host: str,
    records: list[ProcessRecord],
) -> LaunchState:
    return LaunchState(
        app_version=APP_VERSION,
        mode=mode,
        host=host,
        started_at=_now(),
        launcher_pid=os.getpid(),
        processes=records,
    )


def backend_command(*, host: str, port: int, reload: bool) -> list[str]:
    """uvicorn invocation for the current interpreter."""
    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "api.server:app",
        "--host",
        host,
        "--port",
        str(port),
    ]
    if reload:
        command.append("--reload")
    return command


VITE_BIN = paths.WEB_NODE_MODULES / "vite" / "bin" / "vite.js"


def frontend_command(*, host: str, port: int) -> list[str]:
    """Vite dev server invocation.

    Vite is launched through `node` directly rather than `npm run dev` so the
    PID we record *is* the server. Going through the `npm.cmd` shim makes the
    real Vite process a grandchild, and the shim exits immediately -- which
    leaves `stop` with a dead PID and no reliable handle on the live server.

    `--host` is passed explicitly because Vite otherwise binds the `localhost`
    name, which on Windows can resolve to ::1 only, leaving a health check
    against 127.0.0.1 to time out against a server that is actually running.
    """
    if VITE_BIN.is_file():
        return [
            "node",
            str(VITE_BIN),
            "--host",
            host,
            "--port",
            str(port),
            "--strictPort",
        ]
    # Fallback for an unusual install layout. Functional, but the npm shim means
    # the tracked PID may exit early and leave the server to be cleaned up by
    # the launcher's own shutdown rather than by `stop`.
    npm = "npm.cmd" if IS_WINDOWS else "npm"
    return [npm, "run", "dev", "--", "--host", host, "--port", str(port), "--strictPort"]
