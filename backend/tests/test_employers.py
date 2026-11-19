"""Employer registry acceptance tests (issue #35)."""

from collections.abc import Iterator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.scraping import FetchError, Page

PASSWORD = "correct-horse-battery"


@pytest.fixture(scope="session")
def app(engine) -> Iterator[TestClient]:
    yield TestClient(create_app())


def _auth(client: TestClient, email: str) -> dict[str, str]:
    resp = client.post("/auth/register", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _page(url: str) -> Page:
    content = "<html><title>Acme Corp Jobs</title></html>"
    return Page(url=url, content=content, title="Acme Corp Jobs")


def test_register_detects_provider_and_feed_endpoint(app, db_session) -> None:
    with (
        patch(
            "app.api.employers.fetch_page",
            return_value=_page("https://boards.greenhouse.io/acme"),
        ),
        patch("app.scraping.robots_allows", return_value=True),
    ):
        resp = app.post(
            "/employers",
            json={"career_url": "https://boards.greenhouse.io/acme"},
            headers=_auth(app, "emp-alice@example.com"),
        )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["ats_provider"] == "GREENHOUSE"
    assert body["feed_endpoint"] == "https://boards-api.greenhouse.io/v1/boards/acme/jobs?content=true"
    assert body["name"] == "Acme Corp Jobs"
    assert body["monitoring_status"] == "active"
    assert "matched GREENHOUSE" in body["detection_evidence"]


def test_register_unknown_provider_still_registers(app, db_session) -> None:
    with (
        patch("app.api.employers.fetch_page", return_value=_page("https://careers.acme.example")),
        patch("app.scraping.robots_allows", return_value=True),
    ):
        resp = app.post(
            "/employers",
            json={"career_url": "https://careers.acme.example", "name": "Acme Independent"},
            headers=_auth(app, "emp-bob@example.com"),
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["ats_provider"] is None
    assert body["monitoring_status"] == "unsupported"


def test_duplicate_registration_rejected(app, db_session) -> None:
    headers = _auth(app, "emp-carol@example.com")
    with (
        patch("app.api.employers.fetch_page", return_value=_page("https://jobs.lever.co/dup")),
        patch("app.scraping.robots_allows", return_value=True),
    ):
        first = app.post(
            "/employers", json={"career_url": "https://jobs.lever.co/dup"}, headers=headers
        )
        second = app.post(
            "/employers", json={"career_url": "https://jobs.lever.co/dup/"}, headers=headers
        )
    assert first.status_code == 201
    assert second.status_code == 409
    assert "already registered" in second.json()["detail"]


def test_unreachable_url_clear_error(app, db_session) -> None:
    headers = _auth(app, "emp-dave@example.com")
    with patch(
        "app.api.employers.fetch_page",
        side_effect=FetchError("Career page returned HTTP 503"),
    ):
        resp = app.post(
            "/employers", json={"career_url": "https://careers.down.example"}, headers=headers
        )
    assert resp.status_code == 422
    assert "503" in resp.json()["detail"]


def test_robots_disallow_rejected(app, db_session) -> None:
    headers = _auth(app, "emp-eve@example.com")
    with patch(
        "app.api.employers.fetch_page",
        side_effect=FetchError("robots.txt disallows fetching this page"),
    ):
        resp = app.post(
            "/employers", json={"career_url": "https://careers.private.example"}, headers=headers
        )
    assert resp.status_code == 422
    assert "robots.txt" in resp.json()["detail"]


def test_private_address_rejected_by_url_validation(app, db_session) -> None:
    headers = _auth(app, "emp-frank@example.com")
    with patch("app.scraping.httpx.get") as mock_get:
        mock_get.side_effect = AssertionError("must not fetch")
        resp = app.post("/employers", json={"career_url": "http://localhost:9200"}, headers=headers)
    assert resp.status_code == 422
    assert "non-public" in resp.json()["detail"]


def test_employers_listed_and_isolated_per_user(app, db_session) -> None:
    alice = _auth(app, "emp-grace@example.com")
    with (
        patch("app.api.employers.fetch_page", return_value=_page("https://jobs.lever.co/graceco")),
        patch("app.scraping.robots_allows", return_value=True),
    ):
        app.post("/employers", json={"career_url": "https://jobs.lever.co/graceco"}, headers=alice)
    heidi = _auth(app, "emp-heidi@example.com")
    listed = app.get("/employers", headers=heidi).json()
    assert all(e["career_url"] != "https://jobs.lever.co/graceco" for e in listed)
    mine = app.get("/employers", headers=alice).json()
    assert len(mine) == 1


def test_monitoring_status_patch(app, db_session) -> None:
    headers = _auth(app, "emp-ivan@example.com")
    with (
        patch("app.api.employers.fetch_page", return_value=_page("https://jobs.lever.co/ivanco")),
        patch("app.scraping.robots_allows", return_value=True),
    ):
        created = app.post(
            "/employers", json={"career_url": "https://jobs.lever.co/ivanco"}, headers=headers
        ).json()
    paused = app.patch(
        f"/employers/{created['id']}", json={"monitoring_status": "paused"}, headers=headers
    ).json()
    assert paused["monitoring_status"] == "paused"
    assert app.patch(
        f"/employers/{created['id']}", json={"monitoring_status": "bogus"}, headers=headers
    ).status_code == 422


def test_normalize_url_removes_trailing_slash_and_case(app, db_session) -> None:
    from app.api.employers import normalize_url

    assert (
        normalize_url("https://Jobs.LeVer.co/Company/") == "https://jobs.lever.co/Company"
    )
