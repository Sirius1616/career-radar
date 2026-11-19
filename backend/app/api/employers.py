"""Employer registry API: register employers by official career-page URL."""

import re
import uuid
from datetime import UTC, datetime
from typing import Literal
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.auth import get_current_user
from app.db import session_scope
from app.models.employer import Employer
from app.models.user import User
from app.providers.detection import UNKNOWN, detect_from_page
from app.scraping import FetchError, fetch_page

router = APIRouter(prefix="/employers", tags=["employers"])


class EmployerIn(BaseModel):
    career_url: HttpUrl
    name: str | None = Field(default=None, max_length=200)


class EmployerPatch(BaseModel):
    monitoring_status: Literal["active", "paused", "unsupported", "error"]


class EmployerOut(BaseModel):
    id: uuid.UUID
    name: str
    career_url: str
    ats_provider: str | None
    feed_endpoint: str | None
    monitoring_status: str
    detection_evidence: str | None
    last_checked_at: datetime | None


def normalize_url(raw_url: str) -> str:
    parts = urlsplit(str(raw_url))
    path = re.sub(r"/+$", "", parts.path.rstrip("/"))
    return f"{parts.scheme.lower()}://{parts.netloc.lower()}{path}"


def _employer_to_out(employer: Employer) -> EmployerOut:
    return EmployerOut(
        id=employer.id,
        name=employer.name,
        career_url=employer.career_url,
        ats_provider=employer.ats_provider,
        feed_endpoint=employer.feed_endpoint,
        monitoring_status=employer.monitoring_status,
        detection_evidence=employer.detection_evidence,
        last_checked_at=employer.last_checked_at,
    )


@router.post("", response_model=EmployerOut, status_code=201)
def register_employer(
    payload: EmployerIn, user: User = Depends(get_current_user)
) -> EmployerOut:
    career_url = str(payload.career_url)
    normalized = normalize_url(career_url)
    try:
        page = fetch_page(career_url)
    except FetchError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except httpx.HTTPError:
        raise HTTPException(
            status_code=422, detail="Career page could not be retrieved"
        ) from None

    detection = detect_from_page(career_url, page.content)
    name = payload.name or page.title or urlsplit(career_url).netloc

    with session_scope() as session:
        duplicate = session.scalar(
            select(Employer).where(Employer.normalized_url == normalized)
        )
        if duplicate is not None:
            raise HTTPException(status_code=409, detail="Employer already registered")
        employer = Employer(
            created_by=user.id,
            name=name,
            career_url=career_url,
            normalized_url=normalized,
            ats_provider=None if detection.provider == UNKNOWN else detection.provider,
            feed_endpoint=detection.feed_endpoint,
            monitoring_status="active" if detection.provider != UNKNOWN else "unsupported",
            detection_evidence=detection.evidence,
            last_checked_at=datetime.now(UTC),
        )
        session.add(employer)
        try:
            session.flush()
        except IntegrityError:
            raise HTTPException(
                status_code=409, detail="Employer already registered"
            ) from None
        return _employer_to_out(employer)


@router.get("", response_model=list[EmployerOut])
def list_employers(user: User = Depends(get_current_user)) -> list[EmployerOut]:
    with session_scope() as session:
        employers = session.scalars(
            select(Employer).where(Employer.created_by == user.id).order_by(Employer.name)
        ).all()
        return [_employer_to_out(e) for e in employers]


@router.patch("/{employer_id}", response_model=EmployerOut)
def patch_employer(
    employer_id: uuid.UUID,
    payload: EmployerPatch,
    user: User = Depends(get_current_user),
) -> EmployerOut:
    with session_scope() as session:
        employer = session.get(Employer, employer_id)
        if employer is None or employer.created_by != user.id:
            raise HTTPException(status_code=404, detail="Employer not found")
        employer.monitoring_status = payload.monitoring_status
        return _employer_to_out(employer)
