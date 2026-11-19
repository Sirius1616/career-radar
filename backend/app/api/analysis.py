"""Job analysis endpoints: trigger and inspect structured intelligence."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.db import session_scope
from app.models.analysis import JobAnalysis
from app.models.job import Job
from app.models.user import User
from app.services.analysis import run_job_analysis

router = APIRouter(prefix="/jobs", tags=["analysis"])


class AnalysisOut(BaseModel):
    job_id: uuid.UUID
    verified_fields: dict
    structured_analysis: dict
    ai_model: str | None
    escalations: int
    analysis_failed: bool


def _to_out(analysis: JobAnalysis) -> AnalysisOut:
    import json

    return AnalysisOut(
        job_id=analysis.job_id,
        verified_fields=json.loads(analysis.verified_fields),
        structured_analysis=json.loads(analysis.structured_analysis),
        ai_model=analysis.ai_model,
        escalations=analysis.escalations,
        analysis_failed=analysis.analysis_failed,
    )


def _owned_job(
    session: Session, job_id: uuid.UUID, user_id: uuid.UUID
) -> Job:
    job = session.get(Job, job_id)
    if job is None or job.created_by != user_id:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/{job_id}/analysis", response_model=AnalysisOut)
def analyze_job(
    job_id: uuid.UUID, user: User = Depends(get_current_user)
) -> AnalysisOut:
    with session_scope() as session:
        job = _owned_job(session, job_id, user.id)
        analysis = run_job_analysis(session, job)
        return _to_out(analysis)


@router.get("/{job_id}/analysis", response_model=AnalysisOut)
def get_job_analysis(
    job_id: uuid.UUID, user: User = Depends(get_current_user)
) -> AnalysisOut:
    with session_scope() as session:
        _owned_job(session, job_id, user.id)
        analysis = session.scalar(
            select(JobAnalysis).where(JobAnalysis.job_id == job_id)
        )
        if analysis is None:
            raise HTTPException(status_code=404, detail="Analysis not run yet")
        return _to_out(analysis)
