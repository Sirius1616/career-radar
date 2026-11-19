"""Discovery service: pull employer feeds, normalise and deduplicate jobs.

The same service function backs scheduled runs and manual dashboard triggers.
Per-employer failures are isolated so one broken feed never stops discovery.
"""

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.employer import Employer
from app.models.job import Job
from app.providers import greenhouse, lever
from app.providers.jobs import FeedError, FeedResponse

# Registry of provider -> feed fetcher. Additional providers plug in here.
PROVIDER_FETCHERS = {
    "GREENHOUSE": greenhouse.fetch_greenhouse,
    "LEVER": lever.fetch_lever,
}

# Analysis is enqueued via the durable task queue (Epic 11, #56). Until that
# lands, new jobs are marked status="new" which the analysis pipeline scans.
PENDING_ANALYSIS_STATUS = "new"


@dataclass
class DiscoveryReport:
    employers_processed: int = 0
    employers_failed: list[str] = field(default_factory=list)
    postings_seen: int = 0
    jobs_new: int = 0
    jobs_deduplicated: int = 0
    job_ids: list[uuid.UUID] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "employers_processed": self.employers_processed,
            "employers_failed": self.employers_failed,
            "postings_seen": self.postings_seen,
            "jobs_new": self.jobs_new,
            "jobs_deduplicated": self.jobs_deduplicated,
        }


def make_dedupe_key(employer_id: uuid.UUID, source_url: str) -> str:
    normalised = source_url.strip().rstrip("/").lower()
    digest = hashlib.sha256(f"{employer_id}|{normalised}".encode()).hexdigest()
    return digest


def run_discovery_for_employer(
    session: Session, employer: Employer
) -> tuple[list[Job], int]:
    if not employer.feed_endpoint or employer.ats_provider not in PROVIDER_FETCHERS:
        raise FeedError(f"No supported feed configured for {employer.name}")
    fetcher = PROVIDER_FETCHERS[employer.ats_provider]
    feed: FeedResponse = fetcher(employer.feed_endpoint, employer.name)
    now = datetime.now(UTC)
    stored: list[Job] = []
    metadata = json.dumps(
        {
            "provider": employer.ats_provider,
            "feed_endpoint": employer.feed_endpoint,
            "fetched_at": feed.fetched_at.isoformat(),
        }
    )
    duplicates = 0
    for posting in feed.postings:
        if not posting.source_url or not posting.title:
            continue  # malformed entry; skip without failing the employer
        key = make_dedupe_key(employer.id, posting.source_url)
        existing = session.scalar(select(Job).where(Job.dedupe_key == key))
        if existing is not None:
            existing.last_seen_at = now
            existing.last_checked_at = now
            duplicates += 1
            continue
        job = Job(
            employer_id=employer.id,
            created_by=employer.created_by,
            title=posting.title[:300],
            source_url=posting.source_url,
            dedupe_key=key,
            published_at=posting.published_at,
            first_seen_at=now,
            last_seen_at=now,
            last_checked_at=now,
            status=PENDING_ANALYSIS_STATUS,
            location=posting.location,
            department=posting.department,
            description=posting.description,
            description_format=posting.description_format,
            feed_metadata=metadata,
        )
        session.add(job)
        session.flush()
        stored.append(job)
    return stored, duplicates


def run_discovery(session: Session, user_id: uuid.UUID) -> DiscoveryReport:
    report = DiscoveryReport()
    employers = session.scalars(
        select(Employer).where(
            Employer.created_by == user_id, Employer.monitoring_status == "active"
        )
    ).all()
    for employer in employers:
        report.employers_processed += 1
        try:
            new_jobs, duplicates = run_discovery_for_employer(session, employer)
        except FeedError as exc:
            # Per-employer isolation: record the failure and continue.
            report.employers_failed.append(f"{employer.name}: {exc}")
            continue
        report.postings_seen += len(new_jobs) + duplicates
        report.jobs_deduplicated += duplicates
        for job in new_jobs:
            report.jobs_new += 1
            report.job_ids.append(job.id)
    return report
