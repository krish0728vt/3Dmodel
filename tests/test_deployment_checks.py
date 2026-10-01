from __future__ import annotations

import socket
from collections import namedtuple
from pathlib import Path

import pytest

from deployment import checks
from deployment.models import CheckStatus, DoctorReport


def test_supported_python_passes():
    result = checks.check_python_version()
    assert result.status is CheckStatus.PASS
    assert result.detail.startswith("3.11")


def test_unsupported_python_fails_with_remedy(monkeypatch):
    # sys.version_info cannot be instantiated, so stand in a compatible tuple.
    fake = namedtuple("version_info", "major minor micro releaselevel serial")(3, 9, 7, "final", 0)
    monkeypatch.setattr(checks.sys, "version_info", fake)
    result = checks.check_python_version()
    assert result.status is CheckStatus.FAIL
    assert "3.11" in result.detail
    assert result.remedy and "venv" in result.remedy


def test_virtualenv_warns_outside_venv(monkeypatch):
    monkeypatch.setattr(checks.sys, "prefix", "/usr")
    monkeypatch.setattr(checks.sys, "base_prefix", "/usr")
    result = checks.check_virtualenv()
    assert result.status is CheckStatus.WARN


def test_missing_node_fails(monkeypatch):
    monkeypatch.setattr(checks.shutil, "which", lambda _name: None)
    result = checks.check_node()
    assert result.status is CheckStatus.FAIL
    assert "not found" in result.detail
    assert result.remedy and "nodejs.org" in result.remedy


def test_missing_npm_fails(monkeypatch):
    monkeypatch.setattr(checks.shutil, "which", lambda _name: None)
    result = checks.check_npm()
    assert result.status is CheckStatus.FAIL


def test_old_node_major_fails(monkeypatch):
    monkeypatch.setattr(checks, "_run_tool", lambda _cmd: (True, "v16.20.0"))
    result = checks.check_node()
    assert result.status is CheckStatus.FAIL
    assert "16.20.0" in result.detail


def test_current_node_major_passes(monkeypatch):
    monkeypatch.setattr(checks, "_run_tool", lambda _cmd: (True, "v22.11.0"))
    result = checks.check_node()
    assert result.status is CheckStatus.PASS
    assert result.detail == "22.11.0"


def test_missing_node_modules_fails(monkeypatch, tmp_path):
    lock = tmp_path / "package-lock.json"
    lock.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(checks.paths, "WEB_PACKAGE_LOCK", lock)
    monkeypatch.setattr(checks.paths, "WEB_NODE_MODULES", tmp_path / "node_modules")
    result = checks.check_frontend_dependencies()
    assert result.status is CheckStatus.FAIL
    assert "node_modules" in result.detail


def test_incomplete_node_modules_warns(monkeypatch, tmp_path):
    lock = tmp_path / "package-lock.json"
    lock.write_text("{}", encoding="utf-8")
    node_modules = tmp_path / "node_modules"
    node_modules.mkdir()
    monkeypatch.setattr(checks.paths, "WEB_PACKAGE_LOCK", lock)
    monkeypatch.setattr(checks.paths, "WEB_NODE_MODULES", node_modules)
    result = checks.check_frontend_dependencies()
    assert result.status is CheckStatus.WARN


def test_missing_lockfile_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(checks.paths, "WEB_PACKAGE_LOCK", tmp_path / "absent.json")
    result = checks.check_frontend_dependencies()
    assert result.status is CheckStatus.FAIL
    assert "lockfile" in result.name.lower()


def test_unbuilt_frontend_warns_not_fails(monkeypatch, tmp_path):
    """Dev mode does not need a build, so this must never be fatal."""
    monkeypatch.setattr(checks.paths, "WEB_DIST_DIR", tmp_path / "dist")
    result = checks.check_frontend_build()
    assert result.status is CheckStatus.WARN


def test_built_frontend_passes(monkeypatch, tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html></html>", encoding="utf-8")
    (dist / "assets" / "index-abc.js").write_text("//", encoding="utf-8")
    monkeypatch.setattr(checks.paths, "WEB_DIST_DIR", dist)
    result = checks.check_frontend_build()
    assert result.status is CheckStatus.PASS


def test_writable_directory_passes(tmp_path):
    result = checks.check_writable("tmp", tmp_path / "nested")
    assert result.status is CheckStatus.PASS
    assert not (tmp_path / "nested" / ".shah_write_probe").exists()


def test_unwritable_directory_fails(monkeypatch, tmp_path):
    def deny(*_args, **_kwargs):
        raise OSError(13, "Permission denied")

    monkeypatch.setattr(Path, "write_text", deny)
    result = checks.check_writable("tmp", tmp_path)
    assert result.status is CheckStatus.FAIL
    assert result.remedy


def test_openai_key_missing_warns(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = checks.check_openai_key()
    assert result.status is CheckStatus.WARN
    assert "Manual CAD" in (result.remedy or "")


def test_openai_key_present_passes(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-value")
    result = checks.check_openai_key()
    assert result.status is CheckStatus.PASS
    # The value must never be echoed back.
    assert "test-key-value" not in result.detail


def test_cadquery_import_failure_path(monkeypatch):
    """Simulate a broken CadQuery install without touching the real one."""
    real_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "cadquery":
            raise ImportError("DLL load failed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)
    result = checks.check_cadquery()
    assert result.status is CheckStatus.FAIL
    assert "ImportError" in result.detail


def test_cadquery_real_install_verifies_geometry():
    result = checks.check_cadquery()
    assert result.status is CheckStatus.PASS
    assert "OpenCascade geometry verified" in result.detail


def test_unreadable_database_fails(monkeypatch, tmp_path):
    bad = tmp_path / "shah_projects.db"
    bad.write_bytes(b"this is not a sqlite file")
    monkeypatch.setattr(checks.paths, "DATABASE_FILES", (bad,))
    result = checks.check_databases()
    assert result.status is CheckStatus.FAIL
    assert "never deletes" in (result.remedy or "")


def test_absent_databases_pass(monkeypatch, tmp_path):
    monkeypatch.setattr(checks.paths, "DATABASE_FILES", (tmp_path / "nope.db",))
    result = checks.check_databases()
    assert result.status is CheckStatus.PASS


def test_occupied_port_warns():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        port = sock.getsockname()[1]
        result = checks.check_port("Backend", port)
    assert result.status is CheckStatus.WARN


def test_doctor_report_exit_codes():
    """Warnings alone must not fail scripted callers."""
    warn_only = DoctorReport(
        app_version="0.19.0",
        results=[checks._warn("x", "y"), checks._ok("a", "b")],
    )
    assert warn_only.exit_code == 0
    assert warn_only.overall == "READY WITH WARNINGS"

    with_failure = DoctorReport(
        app_version="0.19.0",
        results=[checks._fail("x", "y"), checks._ok("a", "b")],
    )
    assert with_failure.exit_code == 1
    assert with_failure.overall == "NOT READY"

    clean = DoctorReport(app_version="0.19.0", results=[checks._ok("a", "b")])
    assert clean.exit_code == 0
    assert clean.overall == "READY"


def test_run_doctor_is_read_only(tmp_path, monkeypatch):
    """doctor must not create or modify databases."""
    data_dir = tmp_path / "data"
    monkeypatch.setattr(checks.paths, "DATA_DIR", data_dir)
    monkeypatch.setattr(checks.paths, "OUTPUTS_DIR", tmp_path / "outputs")
    monkeypatch.setattr(checks.paths, "RUNTIME_DIR", tmp_path / "runtime")
    monkeypatch.setattr(checks.paths, "DATABASE_FILES", ())
    report = checks.run_doctor(include_ports=False)
    assert isinstance(report, DoctorReport)
    # Write probes are cleaned up, so no stray files remain.
    assert not list(data_dir.glob(".shah_write_probe"))


def test_format_report_shows_remedies_only_for_problems():
    report = DoctorReport(
        app_version="0.19.0",
        build="abc1234",
        results=[
            checks._ok("Fine", "all good"),
            checks._warn("Iffy", "not set", "Do the thing"),
        ],
    )
    text = checks.format_report(report)
    assert "[PASS] Fine" in text
    assert "[WARN] Iffy" in text
    assert "Do the thing" in text
    assert "abc1234" in text
    assert "READY WITH WARNINGS" in text


@pytest.mark.parametrize("status", [CheckStatus.PASS, CheckStatus.WARN, CheckStatus.FAIL])
def test_check_status_round_trips(status):
    result = checks.CheckResult(name="n", status=status, detail="d")
    assert result.is_blocking is (status is CheckStatus.FAIL)


def test_doctor_can_skip_frontend_checks(monkeypatch, tmp_path):
    """Backend-only environments (CI) must not fail on a missing node_modules."""
    monkeypatch.setattr(checks.paths, "WEB_NODE_MODULES", tmp_path / "absent")
    monkeypatch.setattr(checks.paths, "WEB_PACKAGE_LOCK", tmp_path / "absent.json")
    monkeypatch.setattr(checks.paths, "WEB_DIST_DIR", tmp_path / "no-dist")

    with_frontend = checks.run_doctor(include_ports=False, include_frontend=True)
    assert with_frontend.exit_code == 1

    without_frontend = checks.run_doctor(include_ports=False, include_frontend=False)
    assert without_frontend.exit_code == 0
    names = {result.name for result in without_frontend.results}
    assert "Node.js" not in names
    assert "Frontend dependencies" not in names
    # Backend checks are still present.
    assert "CadQuery" in names
    assert "Databases" in names


def test_doctor_can_skip_port_checks():
    names = {r.name for r in checks.run_doctor(include_ports=False).results}
    assert not any(name.startswith("Backend port") for name in names)


def test_placeholder_api_key_counts_as_unconfigured(monkeypatch):
    """A key left at the .env.example placeholder must not claim AI works.

    Otherwise the app reports AI as available and then fails on the first
    request with an auth error.
    """
    from config import openai_key_configured

    # load_dotenv would otherwise re-read a real .env during the test.
    monkeypatch.setattr("dotenv.load_dotenv", lambda *_a, **_k: False)

    for placeholder in ("", "   ", "your_api_key_here", "YOUR-API-KEY-HERE", "changeme", "none"):
        monkeypatch.setenv("OPENAI_API_KEY", placeholder)
        assert openai_key_configured() is False, placeholder

    monkeypatch.setenv("OPENAI_API_KEY", "a-non-placeholder-test-value")
    assert openai_key_configured() is True

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert openai_key_configured() is False


def test_doctor_warns_for_a_placeholder_key(monkeypatch):
    monkeypatch.setattr("dotenv.load_dotenv", lambda *_a, **_k: False)
    monkeypatch.setenv("OPENAI_API_KEY", "your_api_key_here")
    assert checks.check_openai_key().status is CheckStatus.WARN


def test_env_example_ships_a_blank_key():
    """The example must not carry a value that looks configured."""
    from deployment import paths

    text = paths.ENV_EXAMPLE_PATH.read_text(encoding="utf-8")
    line = next(
        raw.strip()
        for raw in text.splitlines()
        if raw.strip().startswith("OPENAI_API_KEY=")
    )
    assert line == "OPENAI_API_KEY="
