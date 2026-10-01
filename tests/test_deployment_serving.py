from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.server import create_app
from api.static_frontend import dist_is_built
from shah_version import APP_VERSION, SCHEMA_VERSION


INDEX_HTML = "<!doctype html><html><head><title>SHAH</title></head><body><div id=root></div></body></html>"


@pytest.fixture
def built_dist(tmp_path):
    """A minimal but realistic Vite dist tree."""
    dist = tmp_path / "dist"
    assets = dist / "assets"
    assets.mkdir(parents=True)
    (dist / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    (assets / "index-abc123.js").write_text("console.log('shah');", encoding="utf-8")
    (assets / "index-abc123.css").write_text("body{margin:0}", encoding="utf-8")
    (dist / "shah-industries-logo.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    return dist


@pytest.fixture
def static_client(built_dist):
    return TestClient(create_app(built_dist))


@pytest.fixture
def api_only_client():
    return TestClient(create_app())


# --------------------------------------------------------------------------
# Version: single source of truth
# --------------------------------------------------------------------------


def test_version_endpoint_reports_app_version(api_only_client):
    response = api_only_client.get("/api/version")
    assert response.status_code == 200
    payload = response.json()
    assert payload["app_version"] == APP_VERSION
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["python_version"].startswith("3.11")
    assert "CadQuery" in payload["cad_engine"]


def test_version_endpoint_never_leaks_the_api_key(api_only_client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-should-never-appear")
    response = api_only_client.get("/api/version")
    body = response.text
    assert response.json()["ai_configured"] is True
    assert "sk-should-never-appear" not in body


def test_version_endpoint_reports_ai_unconfigured(api_only_client, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert api_only_client.get("/api/version").json()["ai_configured"] is False


def test_openapi_version_matches_single_source(api_only_client):
    assert api_only_client.get("/openapi.json").json()["info"]["version"] == APP_VERSION


def test_cli_version_matches_api(api_only_client):
    """The CLI and the API must report the same version string."""
    import app as app_module

    assert app_module.main(["version"]) == 0
    assert api_only_client.get("/api/version").json()["app_version"] == APP_VERSION


# --------------------------------------------------------------------------
# Static SPA serving
# --------------------------------------------------------------------------


def test_dist_is_built_detects_missing_index(tmp_path):
    assert dist_is_built(tmp_path) is False
    (tmp_path / "index.html").write_text("x", encoding="utf-8")
    assert dist_is_built(tmp_path) is True


def test_api_only_app_does_not_serve_frontend(api_only_client):
    """Without a dist directory the app must stay API-only."""
    assert api_only_client.get("/").status_code == 404


def test_root_serves_the_frontend(static_client):
    response = static_client.get("/")
    assert response.status_code == 200
    assert "<div id=root>" in response.text


def test_health_still_works_behind_static_mount(static_client):
    response = static_client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "online"


def test_version_still_works_behind_static_mount(static_client):
    assert static_client.get("/api/version").status_code == 200


def test_deep_spa_route_returns_index(static_client):
    """Frontend deep links must not 404."""
    response = static_client.get("/projects/some-project-id")
    assert response.status_code == 200
    assert "<div id=root>" in response.text


def test_nested_deep_spa_route_returns_index(static_client):
    response = static_client.get("/projects/abc/revisions/3")
    assert response.status_code == 200
    assert "<div id=root>" in response.text


def test_hashed_asset_is_served(static_client):
    response = static_client.get("/assets/index-abc123.js")
    assert response.status_code == 200
    assert "console.log" in response.text


def test_root_level_static_file_is_served(static_client):
    response = static_client.get("/shah-industries-logo.png")
    assert response.status_code == 200
    assert response.content.startswith(b"\x89PNG")


def test_missing_asset_returns_404(static_client):
    """A typo'd asset must 404 rather than silently render the SPA shell."""
    assert static_client.get("/assets/does-not-exist.js").status_code == 404


def test_missing_root_file_with_extension_returns_404(static_client):
    assert static_client.get("/nope.js").status_code == 404


def test_unknown_api_route_returns_404_not_index(static_client):
    """The SPA catch-all must never shadow the API namespace."""
    response = static_client.get("/api/definitely-not-a-route")
    assert response.status_code == 404
    assert "<div id=root>" not in response.text


def test_bare_api_path_returns_404(static_client):
    response = static_client.get("/api")
    assert response.status_code == 404
    assert "<div id=root>" not in response.text


def test_path_traversal_is_refused(static_client):
    """A traversal attempt must not escape dist/ and read arbitrary files."""
    response = static_client.get("/../../requirements.txt")
    assert response.status_code in {200, 404}
    if response.status_code == 200:
        # If anything is served it must be the SPA shell, never file contents.
        assert "cadquery" not in response.text.lower()


def test_existing_api_routes_are_unaffected_by_mounting(static_client, api_only_client):
    """Mounting the frontend must not change the API surface."""
    static_paths = set(static_client.get("/openapi.json").json()["paths"])
    api_paths = set(api_only_client.get("/openapi.json").json()["paths"])
    assert api_paths <= static_paths
    assert "/api/health" in static_paths
    assert "/api/projects" in static_paths


def test_project_download_routes_remain_registered(static_client):
    """Download endpoints must survive the static mount (Part 42)."""
    paths = static_client.get("/openapi.json").json()["paths"]
    assert "/api/projects/{project_id}/download/step" in paths
    assert "/api/projects/{project_id}/download/stl" in paths


def test_mounting_an_unbuilt_dist_is_ignored(tmp_path):
    """create_app must not fail when dist does not exist yet."""
    client = TestClient(create_app(tmp_path / "never-built"))
    assert client.get("/api/health").status_code == 200
    assert client.get("/").status_code == 404
