"""Normalised job-posting DTO and the shared feed-client contract.

The DTO in this module is the only contract downstream services (discovery,
analysis, matching) see. Provider-specific payload shapes never leak.
"""

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx

MAX_ATTEMPTS = 3
BACKOFF_BASE_SECONDS = 0.5
MIN_HOST_INTERVAL_SECONDS = 1.0

_last_request_at: dict[str, float] = {}


class FeedError(Exception):
    """A feed could not be retrieved. Callers should schedule a retry."""


@dataclass(frozen=True)
class JobPosting:
    employer_name: str
    title: str
    source_url: str
    external_id: str
    description: str
    description_format: str  # "html" | "text"
    fetched_at: datetime
    location: str | None = None
    department: str | None = None
    published_at: datetime | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FeedResponse:
    postings: list[JobPosting]
    fetched_at: datetime
    feed_endpoint: str


def _throttle(host: str) -> None:
    """Polite per-host rate limiting: one request per MIN_HOST_INTERVAL."""
    import threading

    lock = threading.Lock()
    with lock:
        now = time.monotonic()
        last = _last_request_at.get(host)
        if last is not None:
            wait = MIN_HOST_INTERVAL_SECONDS - (now - last)
            if wait > 0:
                time.sleep(wait)
        _last_request_at[host] = time.monotonic()


def fetch_json(feed_endpoint: str) -> Any:
    """GET a public feed endpoint with per-host throttling and backoff.

    Raises FeedError (never httpx exceptions) so callers can retry safely.
    """
    host = httpx.URL(feed_endpoint).host or "unknown"
    for attempt in range(MAX_ATTEMPTS):
        _throttle(host)
        try:
            response = httpx.get(
                feed_endpoint,
                timeout=15.0,
                headers={"User-Agent": "CareerRadar/0.1 (+https://github.com/Sirius1616/career-radar)"},
                follow_redirects=True,
            )
        except httpx.HTTPError as exc:
            if attempt == MAX_ATTEMPTS - 1:
                kind = exc.__class__.__name__
                raise FeedError(f"Feed unreachable: {feed_endpoint} ({kind})") from exc
            time.sleep(BACKOFF_BASE_SECONDS * (2**attempt))
            continue
        if response.status_code in (429, 500, 502, 503, 504):
            if attempt == MAX_ATTEMPTS - 1:
                raise FeedError(f"Feed returned HTTP {response.status_code}: {feed_endpoint}")
            time.sleep(BACKOFF_BASE_SECONDS * (2**attempt))
            continue
        if response.status_code != 200:
            raise FeedError(f"Feed returned HTTP {response.status_code}: {feed_endpoint}")
        return response.json()
    raise FeedError(f"Feed retries exhausted: {feed_endpoint}")


def now_utc() -> datetime:
    return datetime.now(UTC)


def parse_epoch_ms(value: Any) -> datetime | None:
    if not value:
        return None
    return datetime.fromtimestamp(int(value) / 1000, tz=UTC)


def parse_iso(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed
