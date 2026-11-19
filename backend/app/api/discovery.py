"""Manual discovery triggers — scheduled runs call the same service functions."""

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.auth import get_current_user
from app.db import session_scope
from app.models.user import User
from app.services.discovery import DiscoveryReport, run_discovery

router = APIRouter(prefix="/discovery", tags=["discovery"])


class DiscoveryReportOut(BaseModel):
    employers_processed: int
    employers_failed: list[str]
    postings_seen: int
    jobs_new: int
    jobs_deduplicated: int


@router.post("/run", response_model=DiscoveryReportOut)
def trigger_discovery(user: User = Depends(get_current_user)) -> DiscoveryReportOut:
    with session_scope() as session:
        report: DiscoveryReport = run_discovery(session, user.id)
        return DiscoveryReportOut(**report.to_dict())


@router.post("/employers/{employer_id}/run", response_model=DiscoveryReportOut)
def trigger_employer_discovery(
    employer_id: uuid.UUID, user: User = Depends(get_current_user)
) -> DiscoveryReportOut:
    from app.models.employer import Employer
    from app.providers.jobs import FeedError
    from app.services.discovery import run_discovery_for_employer

    with session_scope() as session:
        employer = session.get(Employer, employer_id)
        if employer is None or employer.created_by != user.id:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Employer not found")
        try:
            new_jobs, duplicates = run_discovery_for_employer(session, employer)
        except FeedError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        report = DiscoveryReport()
        report.employers_processed = 1
        report.postings_seen = len(new_jobs) + duplicates
        report.jobs_new = len(new_jobs)
        report.jobs_deduplicated = duplicates
        return DiscoveryReportOut(**report.to_dict())
