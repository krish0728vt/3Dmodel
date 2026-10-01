from __future__ import annotations

import socket

import pytest

from deployment import launcher, paths, ports, processes
from deployment.models import LaunchMode, LaunchState, LocalConfig, ProcessRecord


# --------------------------------------------------------------------------
# Ports
# --------------------------------------------------------------------------


@pytest.fixture
def occupied_port():
    """Bind a real listener so the port is genuinely unavailable."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        yield sock.getsockname()[1]


def test_free_port_is_available():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    # Socket is closed, so the port is free again.
    assert ports.is_port_available(port) is True


def test_occupied_port_is_unavailable(occupied_port):
    assert ports.is_port_available(occupied_port) is False


def test_resolve_port_returns_requested_when_free():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    assert ports.resolve_port(port, flag="--backend-port") == port


def test_resolve_port_raises_actionable_error_when_busy(occupied_port):
    with pytest.raises(ports.PortUnavailableError) as excinfo:
        ports.resolve_port(occupied_port, flag="--backend-port")
    message = str(excinfo.value)
    assert "--backend-port" in message
    assert "already in use" in message
    # The launcher must never offer to kill the holder.
    assert "never terminates" in message


def test_resolve_port_finds_alternative_when_auto(occupied_port):
    chosen = ports.resolve_port(occupied_port, flag="--backend-port", auto=True)
    assert chosen != occupied_port
    assert ports.is_port_available(chosen)


def test_find_available_port_gives_up_gracefully(monkeypatch):
    monkeypatch.setattr(ports, "is_port_available", lambda *_a, **_k: False)
    assert ports.find_available_port(9000, attempts=3) is None


def test_find_available_port_respects_upper_bound(monkeypatch):
    monkeypatch.setattr(ports, "is_port_available", lambda *_a, **_k: False)
    assert ports.find_available_port(65535, attempts=5) is None


# --------------------------------------------------------------------------
# Process state file
# --------------------------------------------------------------------------


@pytest.fixture
def isolated_state(tmp_path, monkeypatch):
    """Point the state file at a temp dir so tests never touch runtime/."""
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    state_path = runtime / "shah_processes.json"
    monkeypatch.setattr(paths, "RUNTIME_DIR", runtime)
    monkeypatch.setattr(paths, "PROCESS_STATE_PATH", state_path)
    monkeypatch.setattr(processes.paths, "RUNTIME_DIR", runtime)
    monkeypatch.setattr(processes.paths, "PROCESS_STATE_PATH", state_path)
    return state_path


def _record(name: str = "backend", pid: int = 4242, port: int = 8000) -> ProcessRecord:
    return ProcessRecord(name=name, pid=pid, port=port, command=["x"], log_path="runtime/logs/x.log")


def test_state_round_trips(isolated_state):
    state = processes.build_state(
        mode=LaunchMode.DEV, host="127.0.0.1", records=[_record(), _record("frontend", 4243, 5173)]
    )
    processes.write_state(state)
    assert isolated_state.exists()

    loaded = processes.read_state()
    assert loaded is not None
    assert loaded.mode is LaunchMode.DEV
    assert loaded.process("backend").pid == 4242
    assert loaded.process("frontend").port == 5173
    assert loaded.process("missing") is None


def test_read_state_returns_none_when_absent(isolated_state):
    assert processes.read_state() is None


def test_read_state_tolerates_corrupt_file(isolated_state):
    isolated_state.write_text("{not json", encoding="utf-8")
    assert processes.read_state() is None


def test_clear_state_is_idempotent(isolated_state):
    processes.clear_state()
    processes.write_state(
        processes.build_state(mode=LaunchMode.PRODUCTION, host="127.0.0.1", records=[])
    )
    processes.clear_state()
    assert not isolated_state.exists()
    processes.clear_state()


def test_stale_pid_is_not_treated_as_running(isolated_state):
    """An unused high PID must never be reported as a live process."""
    record = _record(pid=999_999)
    assert processes.pid_is_running(record.pid) is False
    assert processes.is_tracked_process_valid(record) is False


def test_stop_process_reports_already_exited_for_dead_pid():
    assert processes.stop_process(_record(pid=999_999)) == "already-exited"


def test_stop_process_refuses_unrelated_process(monkeypatch):
    """A recycled PID belonging to another program must be left alone."""
    monkeypatch.setattr(processes, "pid_is_running", lambda _pid: True)
    monkeypatch.setattr(processes, "is_tracked_process_valid", lambda _record: False)

    killed: list[int] = []
    monkeypatch.setattr(processes, "_windows_kill_tree", lambda pid, **_kw: killed.append(pid))
    monkeypatch.setattr(processes, "_posix_stop", lambda pid, **_kw: killed.append(pid))

    assert processes.stop_process(_record(pid=1234)) == "stale"
    assert killed == []


def test_pid_zero_and_negative_are_never_running():
    assert processes.pid_is_running(0) is False
    assert processes.pid_is_running(-1) is False


def test_is_tracked_process_valid_rejects_wrong_image(monkeypatch):
    """Guards against PID reuse by an unrelated program on Windows."""
    monkeypatch.setattr(processes, "IS_WINDOWS", True)
    monkeypatch.setattr(processes, "pid_is_running", lambda _pid: True)
    monkeypatch.setattr(processes, "_windows_image_name", lambda _pid: "notepad.exe")
    assert processes.is_tracked_process_valid(_record("backend")) is False


def test_is_tracked_process_valid_accepts_expected_image(monkeypatch):
    monkeypatch.setattr(processes, "IS_WINDOWS", True)
    monkeypatch.setattr(processes, "pid_is_running", lambda _pid: True)
    monkeypatch.setattr(processes, "_windows_image_name", lambda _pid: "python.exe")
    assert processes.is_tracked_process_valid(_record("backend")) is True


def test_frontend_accepts_node_image(monkeypatch):
    monkeypatch.setattr(processes, "IS_WINDOWS", True)
    monkeypatch.setattr(processes, "pid_is_running", lambda _pid: True)
    monkeypatch.setattr(processes, "_windows_image_name", lambda _pid: "node.exe")
    assert processes.is_tracked_process_valid(_record("frontend", 5, 5173)) is True


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------


def test_backend_command_uses_current_interpreter():
    command = processes.backend_command(host="127.0.0.1", port=8123, reload=False)
    assert command[1:3] == ["-m", "uvicorn"]
    assert "api.server:app" in command
    assert "8123" in command
    assert "--reload" not in command


def test_backend_command_adds_reload_in_dev():
    command = processes.backend_command(host="127.0.0.1", port=8000, reload=True)
    assert "--reload" in command


def test_frontend_command_pins_port_strictly():
    """--strictPort stops Vite silently drifting to another port."""
    command = processes.frontend_command(host="127.0.0.1", port=5199)
    assert "5199" in command
    assert "--strictPort" in command


def test_frontend_command_launches_vite_directly():
    """The tracked PID must be the server, not an npm shim.

    Going through `npm run dev` makes Vite a grandchild and the shim exits at
    once, leaving `stop` holding a dead PID with no handle on the live server.
    """
    command = processes.frontend_command(host="127.0.0.1", port=5173)
    if processes.VITE_BIN.is_file():
        assert command[0] == "node"
        assert command[1].endswith("vite.js")
    else:  # pragma: no cover - only on an unusual install layout
        assert command[0] in {"npm", "npm.cmd"}


def test_frontend_command_binds_the_probed_host():
    """Vite must bind the interface the health check probes.

    Without an explicit --host, Vite binds the `localhost` name, which can
    resolve to ::1 only on Windows and make a 127.0.0.1 health check time out
    against a server that is actually up.
    """
    command = processes.frontend_command(host="127.0.0.1", port=5173)
    assert "--host" in command
    assert command[command.index("--host") + 1] == "127.0.0.1"


def test_start_process_rejects_missing_executable(tmp_path):
    with pytest.raises(processes.LaunchError) as excinfo:
        processes.start_process(
            name="backend",
            command=["definitely-not-a-real-binary-xyz"],
            cwd=tmp_path,
            log_file=None,
        )
    assert "not found on PATH" in str(excinfo.value)


def test_start_process_rejects_empty_command(tmp_path):
    with pytest.raises(processes.LaunchError):
        processes.start_process(name="backend", command=[], cwd=tmp_path, log_file=None)


# --------------------------------------------------------------------------
# Launcher behavior that does not spawn servers
# --------------------------------------------------------------------------


def test_local_config_defaults_to_localhost():
    config = LocalConfig()
    assert config.backend_host == "127.0.0.1"
    assert config.backend_port == 8000
    assert config.mode is LaunchMode.PRODUCTION


def test_load_local_config_missing_file_uses_defaults(monkeypatch, tmp_path):
    monkeypatch.setattr(launcher.paths, "LOCAL_CONFIG_PATH", tmp_path / "absent.json")
    assert launcher.load_local_config().backend_port == 8000


def test_load_local_config_reads_overrides(monkeypatch, tmp_path):
    path = tmp_path / "local.json"
    path.write_text('{"backend_port": 9001, "open_browser": false}', encoding="utf-8")
    monkeypatch.setattr(launcher.paths, "LOCAL_CONFIG_PATH", path)
    config = launcher.load_local_config()
    assert config.backend_port == 9001
    assert config.open_browser is False


def test_load_local_config_ignores_comment_keys(monkeypatch, tmp_path):
    """The shipped example file carries a _comment key; it must not break."""
    path = tmp_path / "local.json"
    path.write_text('{"_comment": "notes", "backend_port": 9100}', encoding="utf-8")
    monkeypatch.setattr(launcher.paths, "LOCAL_CONFIG_PATH", path)
    assert launcher.load_local_config().backend_port == 9100


def test_load_local_config_survives_invalid_file(monkeypatch, tmp_path, capsys):
    path = tmp_path / "local.json"
    path.write_text('{"backend_port": "not-a-number"}', encoding="utf-8")
    monkeypatch.setattr(launcher.paths, "LOCAL_CONFIG_PATH", path)
    config = launcher.load_local_config()
    assert config.backend_port == 8000
    assert "ignoring" in capsys.readouterr().out


def test_example_local_config_matches_the_model():
    """The shipped example must stay loadable as the real thing."""
    import json

    raw = json.loads(paths.LOCAL_CONFIG_EXAMPLE_PATH.read_text(encoding="utf-8"))
    cleaned = {k: v for k, v in raw.items() if not k.startswith("_")}
    config = LocalConfig.model_validate(cleaned)
    assert config.backend_host == "127.0.0.1"


def test_status_reports_offline_without_state(isolated_state, capsys):
    assert launcher.status() == 0
    output = capsys.readouterr().out
    assert "Backend: OFFLINE" in output
    assert "No session is recorded" in output


def test_stop_without_state_is_a_noop(isolated_state, capsys):
    assert launcher.stop() == 0
    assert "No SHAH session is recorded" in capsys.readouterr().out


def test_stop_clears_stale_state(isolated_state, capsys):
    processes.write_state(
        processes.build_state(
            mode=LaunchMode.DEV, host="127.0.0.1", records=[_record(pid=999_999)]
        )
    )
    assert launcher.stop() == 0
    output = capsys.readouterr().out
    assert "already exited" in output
    assert not isolated_state.exists()


def test_status_reports_stale_recorded_pid(isolated_state, monkeypatch, capsys):
    processes.write_state(
        processes.build_state(
            mode=LaunchMode.DEV,
            host="127.0.0.1",
            records=[_record(pid=999_999), _record("frontend", 999_998, 5173)],
        )
    )
    monkeypatch.setattr(launcher, "is_tracked_process_valid", lambda _r: False)
    # No live backend, so health probing reports failure.
    monkeypatch.setattr("deployment.health.probe_json", lambda *_a, **_k: None)
    assert launcher.status() == 1
    output = capsys.readouterr().out
    assert "STALE" in output
    assert "API health: FAIL" in output


def test_serve_refuses_when_a_session_is_already_running(isolated_state, monkeypatch, capsys):
    processes.write_state(
        processes.build_state(mode=LaunchMode.DEV, host="127.0.0.1", records=[_record()])
    )
    monkeypatch.setattr(launcher, "_preflight", lambda **_kw: 0)
    monkeypatch.setattr(launcher, "is_tracked_process_valid", lambda _r: True)
    assert launcher.serve(dev=True) == 1
    assert "already running" in capsys.readouterr().out


def test_serve_reports_port_conflict_without_starting(isolated_state, monkeypatch, occupied_port, capsys):
    monkeypatch.setattr(launcher, "_preflight", lambda **_kw: 0)
    started: list[str] = []
    monkeypatch.setattr(launcher, "_run_session", lambda **_kw: started.append("ran") or 0)

    exit_code = launcher.serve(dev=True, backend_port=occupied_port, open_browser=False)
    assert exit_code == 1
    assert started == []
    output = capsys.readouterr().out
    assert "already in use" in output
    assert "--backend-port" in output


def test_serve_production_requires_a_build(isolated_state, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(launcher, "_preflight", lambda **_kw: 0)
    monkeypatch.setattr(launcher.paths, "WEB_DIST_DIR", tmp_path / "dist")
    monkeypatch.setattr(launcher, "_run_session", lambda **_kw: 0)
    # Port availability is irrelevant here and varies by machine, so keep the
    # test focused on the missing-build branch.
    monkeypatch.setattr(launcher, "resolve_port", lambda port, **_kw: port)
    assert launcher.serve(dev=False, open_browser=False) == 1
    output = capsys.readouterr().out
    assert "not built" in output
    assert "python app.py build" in output


def test_clean_is_a_dry_run_without_yes(monkeypatch, tmp_path, capsys):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("x", encoding="utf-8")
    monkeypatch.setattr(
        launcher, "_CLEANABLE", (("frontend build", dist),)
    )
    assert launcher.clean(yes=False) == 0
    assert dist.exists(), "clean must not delete anything without --yes"
    assert "--yes" in capsys.readouterr().out


def test_clean_removes_only_listed_paths(isolated_state, monkeypatch, tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("x", encoding="utf-8")
    protected = tmp_path / "data"
    protected.mkdir()
    (protected / "shah_projects.db").write_text("keep me", encoding="utf-8")
    monkeypatch.setattr(launcher, "_CLEANABLE", (("frontend build", dist),))

    assert launcher.clean(yes=True) == 0
    assert not dist.exists()
    assert (protected / "shah_projects.db").read_text(encoding="utf-8") == "keep me"


def test_cleanable_locations_exclude_user_data():
    """Guards the safety invariant: no database or export path is cleanable."""
    cleanable = {path for _label, path in launcher._CLEANABLE}
    assert paths.DATA_DIR not in cleanable
    assert paths.OUTPUTS_DIR not in cleanable
    assert paths.BACKUPS_DIR not in cleanable
    for database in paths.DATABASE_FILES:
        assert database not in cleanable


def test_backup_excludes_secrets_and_bulk_dirs(monkeypatch, tmp_path):
    import zipfile

    data = tmp_path / "data"
    data.mkdir()
    database = data / "shah_projects.db"
    database.write_text("db", encoding="utf-8")
    secret = tmp_path / ".env"
    secret.write_text("OPENAI_API_KEY=super-secret", encoding="utf-8")

    monkeypatch.setattr(launcher.paths, "BACKUPS_DIR", tmp_path / "backups")
    monkeypatch.setattr(launcher.paths, "DATABASE_FILES", (database,))
    monkeypatch.setattr(launcher.paths, "DATA_DIR", data)
    monkeypatch.setattr(launcher.paths, "MCP_CONFIG_PATH", tmp_path / "absent.json")
    monkeypatch.setattr(launcher.paths, "LOCAL_CONFIG_PATH", tmp_path / "absent-local.json")
    monkeypatch.setattr(launcher.paths, "ENV_PATH", secret)

    assert launcher.backup() == 0
    archives = list((tmp_path / "backups").glob("shah_backup_*.zip"))
    assert len(archives) == 1
    with zipfile.ZipFile(archives[0]) as archive:
        names = archive.namelist()
    assert any("shah_projects.db" in name for name in names)
    assert not any(".env" in name for name in names)
    assert not any("node_modules" in name for name in names)


def test_backup_with_nothing_to_archive(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(launcher.paths, "BACKUPS_DIR", tmp_path / "backups")
    monkeypatch.setattr(launcher.paths, "DATABASE_FILES", ())
    monkeypatch.setattr(launcher.paths, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(launcher.paths, "MCP_CONFIG_PATH", tmp_path / "absent.json")
    monkeypatch.setattr(launcher.paths, "LOCAL_CONFIG_PATH", tmp_path / "absent2.json")
    assert launcher.backup() == 0
    assert "Nothing to back up" in capsys.readouterr().out


def test_public_host_prints_security_warning(capsys):
    launcher._warn_if_public("0.0.0.0")
    output = capsys.readouterr().out
    assert "WARNING" in output
    assert "no authentication" in output


def test_localhost_prints_no_warning(capsys):
    launcher._warn_if_public("127.0.0.1")
    assert capsys.readouterr().out == ""


def test_launch_state_rejects_unknown_process_name():
    with pytest.raises(ValueError):
        LaunchState(
            app_version="0.19.0",
            mode=LaunchMode.DEV,
            host="127.0.0.1",
            started_at="now",
            launcher_pid=1,
            processes=[{"name": "database", "pid": 1, "port": 1}],
        )


# --------------------------------------------------------------------------
# Shutdown contract
# --------------------------------------------------------------------------


class _FakePopen:
    """Minimal Popen stand-in so shutdown can be tested without real servers."""

    def __init__(self, pid: int = 1234, exit_code: int | None = None) -> None:
        self.pid = pid
        self._exit_code = exit_code
        self.terminated = False

    def poll(self) -> int | None:
        return self._exit_code

    def wait(self, timeout: float | None = None) -> int:  # noqa: ARG002
        return self._exit_code or 0

    def terminate(self) -> None:
        self.terminated = True
        self._exit_code = -15

    def kill(self) -> None:
        self.terminated = True
        self._exit_code = -9


def test_ctrl_c_returns_zero_and_stops_children(monkeypatch, capsys):
    """Ctrl+C is a clean shutdown: exit code 0 and no surviving children."""
    backend = _FakePopen(pid=111)
    frontend = _FakePopen(pid=222)
    processes_list = [("backend", backend), ("frontend", frontend)]

    def interrupt(_seconds):
        raise KeyboardInterrupt

    monkeypatch.setattr(launcher.time, "sleep", interrupt)
    assert launcher._wait_until_interrupted(processes_list) == 0
    assert "Shutting down" in capsys.readouterr().out


def test_unexpected_child_exit_is_reported_as_failure(monkeypatch, capsys):
    """A child dying on its own is a failure, not a clean stop."""
    backend = _FakePopen(pid=111, exit_code=3)
    assert launcher._wait_until_interrupted([("backend", backend)]) == 1
    output = capsys.readouterr().out
    assert "exited unexpectedly" in output
    assert "code 3" in output


def test_shutdown_terminates_live_children_and_closes_logs(monkeypatch, capsys):
    stopped: list[int] = []
    monkeypatch.setattr(launcher, "terminate_popen", lambda proc, **_kw: stopped.append(proc.pid))

    class _Log:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    log = _Log()
    children = [("backend", _FakePopen(pid=111)), ("frontend", _FakePopen(pid=222))]
    logs: list[object] = [log]

    launcher._shutdown(children, logs)

    # Reverse order: the frontend is stopped before the backend.
    assert stopped == [222, 111]
    assert log.closed is True
    # Lists are drained so a second call is a no-op.
    assert children == []
    assert logs == []
    launcher._shutdown(children, logs)


def test_shutdown_skips_already_exited_children(monkeypatch):
    stopped: list[int] = []
    monkeypatch.setattr(launcher, "terminate_popen", lambda proc, **_kw: stopped.append(proc.pid))
    launcher._shutdown([("backend", _FakePopen(pid=111, exit_code=0))], [])
    assert stopped == []


def test_console_safe_strips_unencodable_characters(monkeypatch):
    """Vite log glyphs must not crash the failure reporter on a cp1252 console."""
    class _Stdout:
        encoding = "cp1252"

    monkeypatch.setattr(launcher.sys, "stdout", _Stdout())
    # U+279C is what Vite prints and what previously raised UnicodeEncodeError.
    result = launcher._console_safe("  ➜  Local: http://127.0.0.1:5173/")
    assert "Local:" in result
    result.encode("cp1252")


def test_console_safe_preserves_text_on_utf8(monkeypatch):
    class _Stdout:
        encoding = "utf-8"

    monkeypatch.setattr(launcher.sys, "stdout", _Stdout())
    assert "➜" in launcher._console_safe("➜ ready")


def test_log_tail_returns_empty_for_missing_file(tmp_path):
    assert launcher._log_tail(tmp_path / "absent.log") == []


def test_log_tail_sanitizes_and_limits_lines(tmp_path, monkeypatch):
    class _Stdout:
        encoding = "cp1252"

    monkeypatch.setattr(launcher.sys, "stdout", _Stdout())
    log = tmp_path / "frontend.log"
    log.write_text("\n".join(f"line {i} ➜" for i in range(40)), encoding="utf-8")
    tail = launcher._log_tail(log, lines=5)
    assert len(tail) == 5
    for line in tail:
        line.encode("cp1252")
