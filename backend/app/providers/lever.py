"""Lever public postings feed client (api.lever.co)."""

from typing import Any

from app.providers.jobs import (
    FeedResponse,
    JobPosting,
    fetch_json,
    now_utc,
    parse_epoch_ms,
)


def fetch_lever(feed_endpoint: str, employer_name: str) -> FeedResponse:
    fetched_at = now_utc()
    payload: list[dict[str, Any]] = fetch_json(feed_endpoint)
    postings = []
    for job in payload:
        categories = job.get("categories") or {}
        postings.append(
            JobPosting(
                employer_name=employer_name,
                title=str(job.get("text") or "").strip(),
                source_url=str(job.get("hostedUrl") or "").strip(),
                external_id=str(job.get("id")),
                description=str(job.get("descriptionPlain") or job.get("description") or ""),
                description_format="text" if job.get("descriptionPlain") else "html",
                fetched_at=fetched_at,
                location=categories.get("location"),
                department=categories.get("department"),
                published_at=parse_epoch_ms(job.get("createdAt")),
            )
        )
    return FeedResponse(
        postings=postings, fetched_at=fetched_at, feed_endpoint=feed_endpoint
    )
