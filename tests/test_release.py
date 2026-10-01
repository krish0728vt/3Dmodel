"""Release-candidate behavior: version identity, health, API errors, and the
documentation and security guards added for v1.0.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.errors import api_error, error_payload
from api.server import create_app
from shah_version import APP_VERSION, SCHEMA_VERSION, version_line


@pytest.fixture
def client():
    return TestClient(create_app())


# ---------------------------------------------------------------------------
# Version: one source of truth
# ---------------------------------------------------------------------------


def test_version_is_a_valid_release_candidate():
    # Semver with a prerelease tag, e.g. 1.0.0-rc.1
    assert re.fullmatch(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.]+)?", APP_VERSION), APP_VERSION


def test_version_is_the_release_candidate():
    assert APP_VERSION == "1.0.0-rc.1"


def test_version_line_includes_the_name_and_version():
    line = version_line()
    assert "SHAH INDUSTRIES" in line
    assert APP_VERSION in line


def test_cli_api_and_openapi_agree_on_version(client):
    """A single source of truth means these can never disagree."""
    import app as app_module

    assert app_module.main(["version"]) == 0
    assert client.get("/api/version").json()["app_version"] == APP_VERSION
    assert client.get("/openapi.json").json()["info"]["version"] == APP_VERSION
    assert client.get("/api/health").json()["version"] == APP_VERSION


def test_version_is_not_duplicated_in_source():
    """The literal must appear only in shah_version.py."""
    offenders: list[str] = []
    for path in [Path("api/server.py"), Path("api/routes/version.py"), Path("api/routes/health.py")]:
        if APP_VERSION in path.read_text(encoding="utf-8"):
            offenders.append(path.as_posix())
    assert not offenders, f"version literal duplicated in: {offenders}"


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------


def test_health_reports_version_and_cad_readiness(client):
    payload = client.get("/api/health").json()
    assert payload["status"] == "online"
    assert payload["version"] == APP_VERSION
    assert payload["cad_engine_ready"] is True
    assert payload["route_count"] > 50


def test_health_does_not_run_geometry(monkeypatch, client):
    """Health must stay cheap: no kernel call per poll."""
    import cadquery

    calls: list[str] = []
    original = cadquery.Workplane

    def tracking(*args, **kwargs):
        calls.append("workplane")
        return original(*args, **kwargs)

    monkeypatch.setattr(cadquery, "Workplane", tracking)
    client.get("/api/health")
    assert calls == [], "health performed a geometry operation"


def test_health_and_version_share_the_system_tag(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert paths["/api/health"]["get"]["tags"] == ["system"]
    assert paths["/api/version"]["get"]["tags"] == ["system"]


def test_version_endpoint_reports_schema_version(client):
    assert client.get("/api/version").json()["schema_version"] == SCHEMA_VERSION


def test_version_endpoint_never_exposes_a_key(monkeypatch, client):
    monkeypatch.setenv("OPENAI_API_KEY", "a-private-value-not-for-clients")
    body = client.get("/api/version").text
    assert "a-private-value-not-for-clients" not in body
    assert client.get("/api/version").json()["ai_configured"] is True


# ---------------------------------------------------------------------------
# API error shape
# ---------------------------------------------------------------------------


def test_error_payload_shape():
    payload = error_payload("invalid_geometry", "The fillet is too large.", {"operation_id": "f1"})
    assert payload == {
        "error": {
            "code": "invalid_geometry",
            "message": "The fillet is too large.",
            "details": {"operation_id": "f1"},
        }
    }


def test_error_payload_omits_empty_details():
    assert error_payload("export_failure", "Nope") == {
        "error": {"code": "export_failure", "message": "Nope"}
    }


def test_api_error_wraps_the_envelope():
    exc = api_error(422, "invalid_geometry", "Too large", {"operation_id": "f1"})
    assert exc.status_code == 422
    assert exc.detail["error"]["code"] == "invalid_geometry"
    assert exc.detail["error"]["details"] == {"operation_id": "f1"}


def test_error_codes_match_the_frontend_mapping():
    """Backend codes must be ones the UI can translate to plain language."""
    from api import errors

    mapping_source = Path("web/src/components/errorPresentation.ts").read_text(encoding="utf-8")
    codes = [
        value
        for name, value in vars(errors).items()
        if name.startswith("CODE_") and isinstance(value, str)
    ]
    assert codes, "no error codes defined"
    # Codes the UI has no entry for would render as the generic fallback.
    unmapped = [
        code
        for code in codes
        if f"{code}:" not in mapping_source and code not in {"not_found", "ai_not_configured", "ambiguous_request"}
    ]
    assert not unmapped, f"codes with no frontend mapping: {unmapped}"


# ---------------------------------------------------------------------------
# Documentation guards
# ---------------------------------------------------------------------------


def test_readme_stays_within_budget():
    lines = len(Path("README.md").read_text(encoding="utf-8").splitlines())
    assert lines <= 500, f"README.md is {lines} lines"


def test_release_documents_exist():
    for path in ("CHANGELOG.md", "docs/release-candidate.md", "docs/deployment.md"):
        assert Path(path).is_file(), f"{path} is missing"


def test_changelog_names_the_release():
    text = Path("CHANGELOG.md").read_text(encoding="utf-8")
    assert f"## v{APP_VERSION}" in text
    for section in ("### Added", "### Improved", "### Fixed", "### Known Limitations"):
        assert section in text, f"CHANGELOG is missing {section}"


def test_documentation_check_passes():
    """The docs guard itself must be green."""
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "scripts/check_docs.py"], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_no_license_is_claimed_without_a_license_file():
    """Do not advertise a license the repository does not have."""
    has_license = any(Path(".").glob("LICENSE*"))
    readme = Path("README.md").read_text(encoding="utf-8")
    if not has_license:
        assert "## License" not in readme, "README claims a license but no LICENSE file exists"


# ---------------------------------------------------------------------------
# Security guards
# ---------------------------------------------------------------------------


def test_frontend_secret_check_allows_help_text_but_catches_real_secrets():
    """The scanner must distinguish naming a variable from embedding its value."""
    import importlib.util
    import sys

    sys.path.insert(0, "scripts")
    spec = importlib.util.spec_from_file_location("security_check", "scripts/security_check.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def flagged(source: str) -> bool:
        return any(pattern.search(source) for pattern, _ in module.FRONTEND_SECRET_PATTERNS)

    # Legitimate: the UI tells the user which variable to set.
    assert not flagged('const help = "Configure OPENAI_API_KEY in .env";')
    # Real problems.
    assert flagged('const OPENAI_API_KEY = "sk-something";')
    assert flagged("const cfg = { OPENAI_API_KEY: \"abc\" };")
    assert flagged("const k = import.meta.env.VITE_OPENAI_API_KEY;")
    assert flagged('headers: { Authorization: "Bearer abc123" }')


def test_no_dynamic_execution_in_source():
    """No eval, exec, or shell=True anywhere the scanner covers."""
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "scripts/security_check.py"], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_deployment_safety_scan_passes():
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "scripts/deployment_safety.py"], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stdout + result.stderr
