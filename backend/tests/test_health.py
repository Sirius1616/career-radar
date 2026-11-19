import os

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def _settings(database_url: str | None) -> Settings:
    return Settings(
        database_url=database_url,
        environment="test",
        _env_file=None,  # type: ignore[call-arg]
    )


def test_healthz_ok_when_database_unconfigured() -> None:
    client = TestClient(create_app(_settings(None)))
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert resp.json()["database"] == "unconfigured"


@pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"), reason="requires a live DATABASE_URL"
)
def test_healthz_reports_connected_database() -> None:
    client = TestClient(create_app(_settings(os.environ["DATABASE_URL"])))
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["database"] == "connected"
