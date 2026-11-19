from fastapi.testclient import TestClient

from app.main import create_app


def test_healthz_returns_ok_without_database() -> None:
    client = TestClient(create_app())
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert resp.json()["database"] == "unconfigured"
