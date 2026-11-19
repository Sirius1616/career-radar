"""Greenhouse public board feed client (boards-api.greenhouse.io)."""

from typing import Any

from app.providers.jobs import (
    FeedResponse,
    JobPosting,
    fetch_json,
    now_utc,
    parse_iso,
)


def fetch_greenhouse(feed_endpoint: str, employer_name: str) -> FeedResponse:
    fetched_at = now_utc()
    payload: dict[str, Any] = fetch_json(feed_endpoint)
    postings = []
    for job in payload.get("jobs", []):
        departments = job.get("departments") or []
        postings.append(
            JobPosting(
                employer_name=employer_name,
                title=str(job.get("title") or "").strip(),
                source_url=str(job.get("absolute_url") or "").strip(),
                external_id=str(job.get("id")),
                description=str(job.get("content") or ""),
                description_format="html",
                fetched_at=fetched_at,
                location=(job.get("location") or {}).get("name"),
                department=departments[0].get("name") if departments else None,
                published_at=parse_iso(job.get("updated_at") or job.get("first_published")),
            )
        )
    return FeedResponse(
        postings=postings, fetched_at=fetched_at, feed_endpoint=feed_endpoint
    )
