"""Job preferences acceptance tests (issue #32)."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.api.preferences import get_preferences_for_user
from app.main import create_app

PASSWORD = "correct-horse-battery"


@pytest.fixture(scope="session")
def app(engine) -> Iterator[TestClient]:
    yield TestClient(create_app())


def _auth(client: TestClient, email: str) -> dict[str, str]:
    resp = client.post("/auth/register", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _sample(**overrides: object) -> dict:
    prefs = {
        "job_titles": ["Backend Engineer", "Platform Engineer"],
        "required_skills": ["Python", "SQL"],
        "min_experience_years": 2,
        "max_experience_years": 10,
        "countries": ["United Kingdom"],
        "cities": ["London"],
        "remote_ok": True,
        "hybrid_ok": True,
        "onsite_ok": False,
        "relocation_ok": True,
        "visa_sponsorship": "required",
        "min_salary": 45000,
        "employment_type": "full_time",
        "max_posting_age_days": 30,
        "min_match_score": 70,
        "lookback_window": "30d",
        "lookback_from": None,
        "lookback_to": None,
    }
    prefs.update(overrides)
    return prefs


def test_preferences_require_authentication(app) -> None:
    assert app.get("/preferences").status_code == 401
    assert app.put("/preferences", json=_sample()).status_code == 401


def test_upsert_then_get_roundtrip(app) -> None:
    headers = _auth(app, "prefs-alice@example.com")
    put = app.put("/preferences", json=_sample(), headers=headers)
    assert put.status_code == 200, put.text
    got = app.get("/preferences", headers=headers).json()
    assert got["job_titles"] == ["Backend Engineer", "Platform Engineer"]
    assert got["visa_sponsorship"] == "required"
    assert got["min_match_score"] == 70
    assert got["lookback_window"] == "30d"
    assert got["user_id"]


def test_runtime_accessor_used_by_services(app) -> None:
    _auth(app, "prefs-bob@example.com")
    headers = _auth(app, "prefs-carol@example.com")
    app.put("/preferences", json=_sample(), headers=headers)
    carol_id = app.get("/auth/me", headers=headers).json()["id"]
    # The service-facing accessor returns only the saved user's preferences.
    prefs = get_preferences_for_user(carol_id)
    assert prefs is not None
    assert prefs.visa_sponsorship == "required"
    assert prefs.min_experience_years == 2


def test_invalid_values_rejected(app) -> None:
    headers = _auth(app, "prefs-dave@example.com")
    cases = [
        _sample(min_experience_years=12, max_experience_years=5),
        _sample(lookback_window="custom", lookback_from=None, lookback_to=None),
        _sample(lookback_window="custom", lookback_from="2026-12-01", lookback_to="2026-01-01"),
        _sample(visa_sponsorship="maybe"),
        _sample(min_match_score=150),
        _sample(max_posting_age_days=0),
        _sample(employment_type="gig"),
        _sample(lookback_window="45d"),
    ]
    for case in cases:
        resp = app.put("/preferences", json=case, headers=headers)
        assert resp.status_code == 422, case


def test_custom_lookback_window_accepted(app) -> None:
    headers = _auth(app, "prefs-eve@example.com")
    payload = _sample(
        lookback_window="custom", lookback_from="2026-01-01", lookback_to="2026-02-01"
    )
    assert app.put("/preferences", json=payload, headers=headers).status_code == 200
    got = app.get("/preferences", headers=headers).json()
    assert got["lookback_window"] == "custom"
    assert got["lookback_from"] == "2026-01-01"


def test_all_lookback_presets_accepted(app) -> None:
    headers = _auth(app, "prefs-frank@example.com")
    for window in ("24h", "7d", "14d", "30d", "90d"):
        resp = app.put("/preferences", json=_sample(lookback_window=window), headers=headers)
        assert resp.status_code == 200, window


def test_preferences_isolated_per_user(app, db_session) -> None:
    app.put("/preferences", json=_sample(), headers=_auth(app, "prefs-grace@example.com"))
    heidi_headers = _auth(app, "prefs-heidi@example.com")
    assert app.get("/preferences", headers=heidi_headers).status_code == 404
