from __future__ import annotations

from fastapi.testclient import TestClient

from api.dependencies import get_capability_registry, get_learning_store
from api.server import create_app
from capabilities.registry import CapabilityRegistry
from learning.store import LearningStore


def test_capability_api_workflow(tmp_path) -> None:
    registry = CapabilityRegistry(tmp_path / "caps.json")
    learning_store = LearningStore(tmp_path / "learning.db")
    app = create_app()
    app.dependency_overrides[get_capability_registry] = lambda: registry
    app.dependency_overrides[get_learning_store] = lambda: learning_store
    client = TestClient(app)

    sources = client.get("/api/capabilities/sources")
    assert sources.status_code == 200
    assert any(source["source_id"] == "local_adapters" for source in sources.json())

    discovered = client.post("/api/capabilities/discover", json={"source_id": "local_adapters"})
    assert discovered.status_code == 200
    capability_id = discovered.json()[0]["capability_id"]

    assert client.post(f"/api/capabilities/{capability_id}/test").status_code == 200
    assert client.post(f"/api/capabilities/{capability_id}/approve", json={"approved_by": "local_user"}).status_code == 200
    assert client.post(f"/api/capabilities/{capability_id}/enable").status_code == 200

    invoked = client.post(
        f"/api/capabilities/{capability_id}/invoke",
        json={"arguments": {"module_mm": 1.0, "teeth": 20, "thickness_mm": 4.0, "bore_diameter_mm": 3.0}},
    )
    assert invoked.status_code == 200
    assert invoked.json()["result"]["result_type"] == "geometry"

    disabled = client.post(f"/api/capabilities/{capability_id}/disable")
    assert disabled.status_code == 200

    blocked = client.post(
        f"/api/capabilities/{capability_id}/invoke",
        json={"arguments": {"module_mm": 1.0, "teeth": 20, "thickness_mm": 4.0, "bore_diameter_mm": 3.0}},
    )
    assert blocked.status_code == 400
