"""Discovery service acceptance tests (issue #39)."""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.main import create_app
from app.models.job import Job
from app.models.user import User
from app.providers.jobs import FeedError, FeedResponse, JobPosting
from app.services import discovery

PASSWORD = "correct-horse-battery"


@pytest.fixture(scope="session")
def app(engine) -> Iterator[TestClient]:
    yield TestClient(create_app())


def _auth(client: TestClient, email: str) -> dict[str, str]:
    resp = client.post("/auth/register", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _register_employer(
    app: TestClient, headers: dict[str, str], url: str
) -> str:
    from unittest.mock import patch

    from app.scraping import Page

    page = Page(url, "<html><title>E</title></html>", "E")
    with patch("app.api.employers.fetch_page", return_value=page):
        resp = app.post("/employers", json={"career_url": url, "name": url}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _posting(url: str, title: str = "Engineer") -> JobPosting:
    return JobPosting(
        employer_name="E",
        title=title,
        source_url=url,
        external_id=url,
        description="<p>desc</p>",
        description_format="html",
        fetched_at=datetime.now(UTC),
        published_at=datetime.now(UTC),
    )


def _feed_response(*postings: JobPosting) -> FeedResponse:
    return FeedResponse(
        postings=list(postings), fetched_at=datetime.now(UTC), feed_endpoint="https://feed"
    )


def _fetch(employer_name: str, feed_endpoint: str):
    """Stub fetcher used by tests (recorded shapes, no live calls)."""
    raise NotImplementedError


def _set_fetcher(monkeypatch: pytest.MonkeyPatch, provider: str, stub: object) -> None:
    original = discovery.PROVIDER_FETCHERS[provider]
    discovery.PROVIDER_FETCHERS[provider] = stub  # type: ignore[assignment]
    yield
    discovery.PROVIDER_FETCHERS[provider] = original


def test_discovery_stores_jobs_with_provenance(app, db_session: Session) -> None:
    headers = _auth(app, "disc-alice@example.com")
    _register_employer(app, headers, "https://jobs.lever.co/alpha")
    with db_session.begin_nested():
        pass
    # make employer GREENHOUSE type by patching fetcher by provider key
    fetches: list[str] = []

    def stub(feed_endpoint: str, employer_name: str) -> FeedResponse:
        fetches.append(feed_endpoint)
        return _feed_response(_posting("https://jobs.lever.co/alpha/jobs/1"))

    with patch.dict(discovery.PROVIDER_FETCHERS, {"LEVER": stub}):
        resp = app.post("/discovery/run", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["jobs_new"] == 1
    assert body["postings_seen"] == 1

    me = app.get("/auth/me", headers=headers).json()
    job = db_session.scalar(select(Job).where(Job.created_by == uuid.UUID(me["id"])))
    assert job is not None
    assert job.title == "Engineer"
    assert job.source_url == "https://jobs.lever.co/alpha/jobs/1"
    assert job.status == "new"
    assert job.first_seen_at is not None
    assert "provider" in job.feed_metadata
    assert job.dedupe_key


def test_duplicate_run_updates_last_seen_without_new_rows(
    app, db_session: Session
) -> None:
    headers = _auth(app, "disc-bob@example.com")
    _register_employer(app, headers, "https://jobs.lever.co/bravo")

    def stub(feed_endpoint: str, employer_name: str) -> FeedResponse:
        return _feed_response(_posting("https://jobs.lever.co/bravo/jobs/9"))

    me = app.get("/auth/me", headers=headers).json()

    with patch.dict(discovery.PROVIDER_FETCHERS, {"LEVER": stub}):
        first = app.post("/discovery/run", headers=headers).json()
        job_row = db_session.scalar(
            select(Job).where(Job.created_by == uuid.UUID(me["id"]))
        )
        first_seen = job_row.last_seen_at
        second = app.post("/discovery/run", headers=headers).json()

    assert first["jobs_new"] == 1
    assert second["jobs_new"] == 0
    assert second["jobs_deduplicated"] == 1
    jobs = db_session.scalars(select(Job).where(Job.created_by == uuid.UUID(me["id"]))).all()
    assert len(jobs) == 1
    assert jobs[0].last_seen_at >= first_seen


def test_per_employer_failure_isolation(app, db_session: Session) -> None:
    headers = _auth(app, "disc-carol@example.com")
    _register_employer(app, headers, "https://jobs.lever.co/charlie")
    _register_employer(app, headers, "https://jobs.lever.co/delta")

    def broken(feed_endpoint: str, employer_name: str) -> FeedResponse:
        raise FeedError("Feed returned HTTP 503")

    def healthy(feed_endpoint: str, employer_name: str) -> FeedResponse:
        return _feed_response(_posting("https://jobs.lever.co/delta/jobs/2"))

    def dispatch(feed_endpoint: str, employer_name: str) -> FeedResponse:
        if "charlie" in employer_name:
            return broken(feed_endpoint, employer_name)
        return healthy(feed_endpoint, employer_name)

    with patch.dict(discovery.PROVIDER_FETCHERS, {"LEVER": dispatch}):
        report = app.post("/discovery/run", headers=headers).json()

    assert report["employers_processed"] == 2
    assert len(report["employers_failed"]) == 1
    assert "charlie" in report["employers_failed"][0]
    me = app.get("/auth/me", headers=headers).json()
    jobs = db_session.scalars(
        select(Job).where(Job.created_by == uuid.UUID(me["id"]))
    ).all()
    assert len(jobs) == 1
    assert jobs[0].source_url.endswith("/jobs/2")


def test_same_service_available_for_scheduled_runs(app, db_session: Session) -> None:
    headers = _auth(app, "disc-eve@example.com")
    _register_employer(app, headers, "https://jobs.lever.co/echo")
    user_id = app.get("/auth/me", headers=headers).json()["id"]

    def stub(feed_endpoint: str, employer_name: str) -> FeedResponse:
        return _feed_response(_posting("https://jobs.lever.co/echo/jobs/3"))

    with patch.dict(discovery.PROVIDER_FETCHERS, {"LEVER": stub}):
        with db_session.begin():
            user = db_session.get(User, uuid.UUID(user_id))
            direct = discovery.run_discovery(db_session, user.id)  # type: ignore[arg-type]
    assert direct.jobs_new == 1
    assert direct.employers_processed == 1


def test_unsupported_employer_excluded(app, db_session: Session) -> None:
    headers = _auth(app, "disc-frank@example.com")
    _register_employer(app, headers, "https://careers.unknown.example")

    def fail_if_called(feed_endpoint: str, employer_name: str) -> FeedResponse:
        raise AssertionError("unsupported employer must not be fetched")

    with patch.dict(discovery.PROVIDER_FETCHERS, {"LEVER": fail_if_called}):
        report = app.post("/discovery/run", headers=headers).json()
    assert report["employers_processed"] == 0
