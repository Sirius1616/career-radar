"""Profile API acceptance tests (issue #31)."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

PASSWORD = "correct-horse-battery"


@pytest.fixture(scope="session")
def app(engine) -> Iterator[TestClient]:
    yield TestClient(create_app())


def _auth(client: TestClient, email: str) -> dict[str, str]:
    resp = client.post("/auth/register", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _sample_profile(**overrides: object) -> dict:
    profile = {
        "professional_summary": "Backend engineer",
        "skills": [
            {"name": "Python", "category": "language"},
            {"name": "React", "category": "framework"},
        ],
        "experiences": [
            {
                "employer": "Acme Ltd",
                "title": "Backend Engineer",
                "start_date": "2022-01-01",
                "end_date": None,
                "description": None,
            }
        ],
        "education": [
            {
                "institution": "University of Lagos",
                "qualification": "BSc Computer Science",
                "start_date": "2017-09-01",
                "end_date": "2021-06-30",
            }
        ],
        "projects": [{"name": "Portfolio", "description": None, "url": "https://example.com/"}],
        "certifications": [{"name": "AWS CCP", "issuer": "AWS", "issued_on": "2023-05-01"}],
        "achievements": [
            {"description": "Cut API latency", "metric": "p95 -40%", "is_verified": True}
        ],
        "github_url": "https://github.com/johndoe",
        "portfolio_url": None,
        "linkedin_url": None,
    }
    profile.update(overrides)
    return profile


def test_profile_requires_authentication(app) -> None:
    assert app.get("/profile").status_code == 401
    assert app.put("/profile", json=_sample_profile()).status_code == 401


def test_upsert_then_get_persists_all_sections(app) -> None:
    headers = _auth(app, "profile-alice@example.com")
    put = app.put("/profile", json=_sample_profile(), headers=headers)
    assert put.status_code == 200, put.text

    got = app.get("/profile", headers=headers).json()
    assert got["professional_summary"] == "Backend engineer"
    assert {s["name"] for s in got["skills"]} == {"Python", "React"}
    assert got["skills"][0]["category"] in {"skill", "language", "framework", "tool"}
    assert got["experiences"][0]["employer"] == "Acme Ltd"
    assert got["education"][0]["qualification"] == "BSc Computer Science"
    assert got["projects"][0]["url"] == "https://example.com/"
    assert got["certifications"][0]["issuer"] == "AWS"
    assert got["github_url"] == "https://github.com/johndoe"


def test_achievements_always_stored_unverified(app, db_session) -> None:
    headers = _auth(app, "profile-bob@example.com")
    app.put("/profile", json=_sample_profile(), headers=headers)
    got = app.get("/profile", headers=headers).json()
    assert got["achievements"][0]["is_verified"] is False


def test_update_replaces_sections(app) -> None:
    headers = _auth(app, "profile-carol@example.com")
    app.put("/profile", json=_sample_profile(), headers=headers)
    updated = _sample_profile(skills=[{"name": "Go", "category": "language"}])
    app.put("/profile", json=updated, headers=headers)
    got = app.get("/profile", headers=headers).json()
    assert [s["name"] for s in got["skills"]] == ["Go"]


def test_experience_validation_requires_employer_title_dates(app) -> None:
    headers = _auth(app, "profile-dave@example.com")
    base = _sample_profile()
    for field in ("employer", "title", "start_date"):
        experience = base["experiences"][0]
        bad = {**base, "experiences": [{k: v for k, v in experience.items() if k != field}]}
        resp = app.put("/profile", json=bad, headers=headers)
        assert resp.status_code == 422, field


def test_invalid_skill_category_rejected(app) -> None:
    headers = _auth(app, "profile-eve@example.com")
    bad = _sample_profile(skills=[{"name": "Python", "category": "wizardry"}])
    assert app.put("/profile", json=bad, headers=headers).status_code == 422


def test_profiles_are_isolated_per_user(app, db_session) -> None:
    a_headers = _auth(app, "profile-frank@example.com")
    _auth(app, "profile-grace@example.com")
    app.put("/profile", json=_sample_profile(), headers=a_headers)

    other = app.get("/profile", headers=_auth(app, "profile-heidi@example.com"))
    assert other.status_code == 404

    grace_headers = _auth(app, "profile-grace2@example.com")
    grace = app.put("/profile", json=_sample_profile(), headers=grace_headers).json()
    frank = app.get("/profile", headers=a_headers).json()
    assert grace["user_id"] != frank["user_id"]
    assert frank["professional_summary"] == "Backend engineer"


def test_profile_delete(app, db_session) -> None:
    headers = _auth(app, "profile-ivan@example.com")
    app.put("/profile", json=_sample_profile(), headers=headers)
    assert app.delete("/profile", headers=headers).status_code == 204
    assert app.get("/profile", headers=headers).status_code == 404
