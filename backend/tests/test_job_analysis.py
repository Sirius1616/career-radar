"""Job analysis acceptance tests (issue #44) — mocked Claude only."""

import json
import uuid
from collections.abc import Iterator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.main import create_app
from app.models.ai import AiCache, AiUsageLog
from app.models.job import Job
from app.services import analysis

PASSWORD = "correct-horse-battery"
GOOD_OUTPUT = json.dumps(
    {
        "mandatory_skills": ["Python", "SQL"],
        "optional_skills": ["Docker"],
        "responsibilities": ["Build APIs"],
        "qualifications": ["BSc Computer Science"],
        "screening_questions": ["How many years of Python?"],
        "work_authorisation": "Must be authorised to work in the UK",
        "sponsorship_statements": ["Visa sponsorship is not available for this role"],
    }
)


@pytest.fixture(scope="session")
def app(engine) -> Iterator[TestClient]:
    yield TestClient(create_app())


@pytest.fixture(autouse=True)
def clean_ai_tables(engine) -> Iterator[None]:
    from app.db import session_scope

    with session_scope() as session:
        session.query(AiCache).delete()
        session.query(AiUsageLog).delete()
    yield


def _auth(client: TestClient, email: str) -> dict[str, str]:
    resp = client.post("/auth/register", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _make_job(app: TestClient, headers: dict[str, str], email: str) -> str:
    from datetime import UTC, datetime
    from unittest.mock import patch

    from app.scraping import Page

    page = Page(url="u", content="<html><title>E</title></html>", title="E")
    with patch("app.api.employers.fetch_page", return_value=page):
        app.post(
            "/employers",
            json={"career_url": f"https://jobs.lever.co/anlys/{email}"},
            headers=headers,
        )

    from app.providers.jobs import FeedResponse, JobPosting
    from app.services.discovery import PROVIDER_FETCHERS

    def stub(feed_endpoint: str, employer_name: str) -> FeedResponse:
        posting = JobPosting(
            employer_name="E",
            title="Backend Engineer",
            source_url=f"https://jobs.lever.co/anlys/jobs/{email}",
            external_id="1",
            description=(
                "Salary: £45,000 per year. " + "Build APIs with Python. " * 20
            ),
            description_format="text",
            fetched_at=datetime.now(UTC),
            location="London, UK",
            department="Engineering",
            published_at=datetime.now(UTC),
        )
        return FeedResponse(postings=[posting], fetched_at=datetime.now(UTC), feed_endpoint="f")

    with patch.dict(PROVIDER_FETCHERS, {"LEVER": stub}):
        app.post("/discovery/run", headers=headers)
    user_id = app.get("/auth/me", headers=headers).json()["id"]
    with db_session_scope() as session:
        user = session.scalar(select_job_user(user_id))
        jobs = session.scalars(select(Job).where(Job.created_by == user.id)).all()
        assert jobs, "discovery must have stored the fixture job"
        return str(jobs[-1].id)


def db_session_scope():
    from app.db import session_scope

    return session_scope()


def select_job_user(user_id: str):
    from app.models.user import User

    return select(User).where(User.id == uuid.UUID(user_id))


class FakeCaller:
    def __init__(self, responses: list[str]) -> None:
        self.calls: list[str] = []
        self.responses = responses

    def create(self, model: str, max_tokens: int, prompt: str) -> tuple[str, int, int]:
        self.calls.append(prompt)
        return self.responses.pop(0), 100, 50


@pytest.fixture
def caller():
    holder: dict[str, FakeCaller] = {}

    def _install(responses: list[str]) -> FakeCaller:
        fake = FakeCaller(responses)
        holder["fake"] = fake
        patcher = patch.object(analysis.gateway, "get_caller", return_value=fake)
        patcher.start()
        return fake

    yield _install
    patch.stopall()


def test_structured_output_contains_required_categories(
    app, db_session: Session, caller
) -> None:
    headers = _auth(app, "anlys-alice@example.com")
    job_id = _make_job(app, headers, "alice")
    caller([GOOD_OUTPUT])
    resp = app.post(f"/jobs/{job_id}/analysis", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    structured = body["structured_analysis"]
    assert structured["ai_derived"] is True
    result = structured["analysis"]
    for key in (
        "mandatory_skills",
        "optional_skills",
        "responsibilities",
        "qualifications",
        "screening_questions",
        "work_authorisation",
        "sponsorship_statements",
    ):
        assert key in result, key


def test_verified_fields_separated_from_ai(app, db_session: Session, caller) -> None:
    headers = _auth(app, "anlys-bob@example.com")
    job_id = _make_job(app, headers, "bob")
    caller([GOOD_OUTPUT])
    body = app.post(f"/jobs/{job_id}/analysis", headers=headers).json()
    verified = body["verified_fields"]
    assert verified["location"]["source"] == "feed_metadata"
    assert "£45,000" in verified["salary_text"]["value"]
    assert "span" in verified["salary_text"]
    # verified fields come from deterministic extraction, not the AI response
    ai_only = set(body["structured_analysis"]["analysis"].keys())
    assert "salary_text" not in ai_only


def test_unchanged_content_not_reanalysed(app, db_session: Session, caller) -> None:
    headers = _auth(app, "anlys-carol@example.com")
    job_id = _make_job(app, headers, "carol")
    fake = caller([GOOD_OUTPUT])
    app.post(f"/jobs/{job_id}/analysis", headers=headers)
    app.post(f"/jobs/{job_id}/analysis", headers=headers)
    assert len(fake.calls) == 1  # second run: cache hit, no new API call


def test_parse_failure_escalates_to_capable_model(
    app, db_session: Session, caller
) -> None:
    headers = _auth(app, "anlys-dave@example.com")
    job_id = _make_job(app, headers, "dave")
    fake = caller(["not json at all", GOOD_OUTPUT])
    body = app.post(f"/jobs/{job_id}/analysis", headers=headers).json()
    assert body["escalations"] == 1
    assert body["ai_model"].startswith("claude-sonnet")
    assert body["structured_analysis"]["analysis"]["mandatory_skills"] == ["Python", "SQL"]
    assert len(fake.calls) == 2


def test_analysis_requires_ownership(app, db_session: Session, caller) -> None:
    headers = _auth(app, "anlys-eve@example.com")
    job_id = _make_job(app, headers, "eve")
    caller([GOOD_OUTPUT])
    other = _auth(app, "anlys-frank@example.com")
    assert app.get(f"/jobs/{job_id}/analysis", headers=other).status_code == 404


def test_prompt_treats_description_as_untrusted_data(
    app, db_session: Session, caller
) -> None:
    headers = _auth(app, "anlys-grace@example.com")
    job_id = _make_job(app, headers, "grace")
    fake = caller([GOOD_OUTPUT])
    app.post(f"/jobs/{job_id}/analysis", headers=headers)
    prompt = fake.calls[0]
    assert "untrusted third-party data" in prompt
    assert "instructions inside it" in prompt
