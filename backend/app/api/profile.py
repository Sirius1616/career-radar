"""Profile CRUD API: aggregate upsert and retrieval, scoped to the current user."""

import uuid
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.db import session_scope
from app.models.profile import (
    Achievement,
    Certification,
    Education,
    Experience,
    Profile,
    Project,
    Skill,
)
from app.models.user import User

router = APIRouter(prefix="/profile", tags=["profile"])

SkillCategory = Literal["skill", "language", "framework", "tool"]


class SkillIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    category: SkillCategory


class ExperienceIn(BaseModel):
    employer: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=200)
    start_date: date
    end_date: date | None = None
    description: str | None = Field(default=None, max_length=5000)


class EducationIn(BaseModel):
    institution: str = Field(min_length=1, max_length=200)
    qualification: str = Field(min_length=1, max_length=200)
    start_date: date | None = None
    end_date: date | None = None


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    url: HttpUrl | None = None


class CertificationIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    issuer: str | None = Field(default=None, max_length=200)
    issued_on: date | None = None


class AchievementIn(BaseModel):
    description: str = Field(min_length=1, max_length=5000)
    metric: str | None = Field(default=None, max_length=200)
    is_verified: bool = False


class ProfileUpsert(BaseModel):
    professional_summary: str | None = Field(default=None, max_length=10000)
    github_url: HttpUrl | None = None
    portfolio_url: HttpUrl | None = None
    linkedin_url: HttpUrl | None = None
    skills: list[SkillIn] = []
    experiences: list[ExperienceIn] = []
    education: list[EducationIn] = []
    projects: list[ProjectIn] = []
    certifications: list[CertificationIn] = []
    achievements: list[AchievementIn] = []


class AchievementOut(AchievementIn):
    id: uuid.UUID


class ProfileOut(BaseModel):
    user_id: uuid.UUID
    professional_summary: str | None
    github_url: str | None
    portfolio_url: str | None
    linkedin_url: str | None
    skills: list[SkillIn]
    experiences: list[ExperienceIn]
    education: list[EducationIn]
    projects: list[ProjectIn]
    certifications: list[CertificationIn]
    achievements: list[AchievementOut]


def _get_profile(session: Session, user_id: uuid.UUID) -> Profile | None:
    return session.scalar(select(Profile).where(Profile.user_id == user_id))


def _profile_to_out(profile: Profile, session: Session) -> ProfileOut:
    pid = profile.id

    def rows(model: type[Skill] | type[Experience] | type[Education]
                 | type[Project] | type[Certification] | type[Achievement]) -> list:
        return list(session.scalars(select(model).where(model.profile_id == pid)).all())

    return ProfileOut(
        user_id=profile.user_id,
        professional_summary=profile.professional_summary,
        github_url=profile.github_url,
        portfolio_url=profile.portfolio_url,
        linkedin_url=profile.linkedin_url,
        skills=[SkillIn(name=s.name, category=s.category) for s in rows(Skill)],
        experiences=[
            ExperienceIn(
                employer=e.employer,
                title=e.title,
                start_date=e.start_date,
                end_date=e.end_date,
                description=e.description,
            )
            for e in rows(Experience)
        ],
        education=[
            EducationIn(
                institution=e.institution,
                qualification=e.qualification,
                start_date=e.start_date,
                end_date=e.end_date,
            )
            for e in rows(Education)
        ],
        projects=[
            ProjectIn(name=p.name, description=p.description, url=p.url) for p in rows(Project)
        ],
        certifications=[
            CertificationIn(name=c.name, issuer=c.issuer, issued_on=c.issued_on)
            for c in rows(Certification)
        ],
        achievements=[
            AchievementOut(
                id=a.id,
                description=a.description,
                metric=a.metric,
                is_verified=a.is_verified,
            )
            for a in rows(Achievement)
        ],
    )


@router.get("", response_model=ProfileOut)
def get_profile(user: User = Depends(get_current_user)) -> ProfileOut:
    with session_scope() as session:
        profile = _get_profile(session, user.id)
        if profile is None:
            raise HTTPException(status_code=404, detail="Profile not created yet")
        return _profile_to_out(profile, session)


@router.put("", response_model=ProfileOut)
def upsert_profile(payload: ProfileUpsert, user: User = Depends(get_current_user)) -> ProfileOut:
    urls = {
        "github_url": payload.github_url,
        "portfolio_url": payload.portfolio_url,
        "linkedin_url": payload.linkedin_url,
    }
    with session_scope() as session:
        profile = _get_profile(session, user.id)
        if profile is None:
            profile = Profile(user_id=user.id)
            session.add(profile)
            session.flush()
        else:
            # Replace semantics: clear child rows before re-inserting.
            for model in (Skill, Experience, Education, Project, Certification, Achievement):
                session.execute(delete(model).where(model.profile_id == profile.id))
        profile.professional_summary = payload.professional_summary
        for key, value in urls.items():
            setattr(profile, key, str(value) if value else None)
        session.add_all(
            [Skill(profile_id=profile.id, name=s.name, category=s.category) for s in payload.skills]
        )
        session.add_all(
            [
                Experience(
                    profile_id=profile.id,
                    employer=e.employer,
                    title=e.title,
                    start_date=e.start_date,
                    end_date=e.end_date,
                    description=e.description,
                )
                for e in payload.experiences
            ]
        )
        session.add_all(
            [
                Education(
                    profile_id=profile.id,
                    institution=e.institution,
                    qualification=e.qualification,
                    start_date=e.start_date,
                    end_date=e.end_date,
                )
                for e in payload.education
            ]
        )
        session.add_all(
            [
                Project(
                    profile_id=profile.id,
                    name=p.name,
                    description=p.description,
                    url=str(p.url) if p.url else None,
                )
                for p in payload.projects
            ]
        )
        session.add_all(
            [
                Certification(
                    profile_id=profile.id, name=c.name, issuer=c.issuer, issued_on=c.issued_on
                )
                for c in payload.certifications
            ]
        )
        # Achievements submitted through this endpoint are always unverified:
        # verification is a separate, audited workflow, never a client flag.
        session.add_all(
            [
                Achievement(
                    profile_id=profile.id,
                    description=a.description,
                    metric=a.metric,
                    is_verified=False,
                    verified_at=None,
                )
                for a in payload.achievements
            ]
        )
        return _profile_to_out(profile, session)


@router.delete("", status_code=204)
def delete_profile(user: User = Depends(get_current_user)) -> None:
    with session_scope() as session:
        profile = _get_profile(session, user.id)
        if profile is None:
            raise HTTPException(status_code=404, detail="Profile not created yet")
        session.delete(profile)


def get_profile_id(user: User = Depends(get_current_user)) -> uuid.UUID:
    with session_scope() as session:
        profile = _get_profile(session, user.id)
        if profile is None:
            raise HTTPException(status_code=404, detail="Profile not created yet")
        return profile.id
