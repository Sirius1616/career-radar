"""Feed client acceptance tests (issue #37) — recorded fixtures, no live calls."""

import json
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from app.providers import greenhouse, jobs, lever
from app.providers.jobs import FeedError, JobPosting

FIXTURES = Path(__file__).parent / "fixtures"


def _fake_transport(payload: bytes | str, status: int = 200) -> Iterator[None]:
    def handler(*args: object, **kwargs: object) -> httpx.Response:
        return httpx.Response(status, content=payload, request=httpx.Request("GET", "https://x"))

    with patch.object(jobs.httpx, "get", side_effect=handler):
        yield


@pytest.fixture
def greenhouse_feed() -> Iterator[None]:
    payload = (FIXTURES / "greenhouse_board.json").read_text()
    yield from _fake_transport(payload)


@pytest.fixture
def lever_feed() -> Iterator[None]:
    payload = (FIXTURES / "lever_board.json").read_text()
    yield from _fake_transport(payload)


def test_greenhouse_normalises_all_postings(greenhouse_feed) -> None:
    response = greenhouse.fetch_greenhouse(
        "https://boards-api.greenhouse.io/v1/boards/acme/jobs?content=true", "Acme"
    )
    assert len(response.postings) == 2
    for posting in response.postings:
        assert isinstance(posting, JobPosting)
        assert posting.title
        assert posting.source_url.startswith("https://boards.greenhouse.io/acme/jobs/")
        assert posting.fetched_at.tzinfo is not None
        assert posting.external_id
    first = response.postings[0]
    assert first.location == "London, UK"
    assert first.department == "Engineering"
    assert first.description_format == "html"
    assert first.published_at is not None and first.published_at.year == 2026


def test_lever_normalises_all_postings(lever_feed) -> None:
    response = lever.fetch_lever("https://api.lever.co/v0/postings/beta?mode=json", "Beta")
    assert len(response.postings) == 2
    first = response.postings[0]
    assert first.title == "Senior Python Engineer"
    assert first.source_url == "https://jobs.lever.co/beta/abc-123"
    assert first.description_format == "text"
    assert first.published_at is not None and first.published_at.year == 2025
    second = response.postings[1]
    assert second.description_format == "html"
    assert second.location == "Remote"


def test_feed_outage_raises_handled_feed_error() -> None:
    def fail(*args: object, **kwargs: object) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    with patch.object(jobs.httpx, "get", side_effect=fail), patch.object(jobs.time, "sleep"):
        with pytest.raises(FeedError):
            jobs.fetch_json("https://boards-api.greenhouse.io/v1/boards/acme/jobs")


def test_server_error_retries_then_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts: list[int] = []
    responses = [httpx.Response(503, request=httpx.Request("GET", "https://x")) for _ in range(3)]

    def handler(*args: object, **kwargs: object) -> httpx.Response:
        attempts.append(1)
        return responses.pop(0)

    sleeps: list[float] = []
    monkeypatch.setattr(jobs.time, "sleep", sleeps.append)
    with patch.object(jobs.httpx, "get", side_effect=handler):
        with pytest.raises(FeedError):
            jobs.fetch_json("https://api.lever.co/v0/postings/beta?mode=json")
    assert len(attempts) == 3
    assert any(abs(wait - 0.5) < 1e-6 for wait in sleeps)
    assert any(abs(wait - 1.0) < 1e-6 for wait in sleeps)


def test_429_retries_and_recovers(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = [
        httpx.Response(429, request=httpx.Request("GET", "https://x")),
        httpx.Response(
            200,
            content=json.dumps({"jobs": []}).encode(),
            request=httpx.Request("GET", "https://x"),
        ),
    ]
    monkeypatch.setattr(jobs.time, "sleep", lambda seconds: None)
    with patch.object(jobs.httpx, "get", side_effect=lambda *a, **kw: responses.pop(0)):
        payload = jobs.fetch_json("https://boards-api.greenhouse.io/v1/boards/acme/jobs")
    assert payload == {"jobs": []}


def test_per_host_throttle_sleeps_between_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr(jobs.time, "sleep", sleeps.append)
    monkeypatch.setattr(jobs.time, "monotonic", [0.0, 0.1, 0.1, 0.1].pop)
    def ok(*args: object, **kwargs: object) -> httpx.Response:
        return httpx.Response(200, content=b"{}", request=httpx.Request("GET", "https://x"))

    with patch.object(jobs.httpx, "get", side_effect=ok):
        jobs.fetch_json("https://boards-api.greenhouse.io/v1/boards/acme/jobs")
        jobs.fetch_json("https://boards-api.greenhouse.io/v1/boards/acme/jobs")
    assert any(wait > 0 for wait in sleeps)
