"""Job preferences API: get/put/delete for the current user's preferences."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select

from app.api.auth import get_current_user
from app.db import session_scope
from app.models.preferences import JobPreferences
from app.models.user import User

router = APIRouter(prefix="/preferences", tags=["preferences"])

WorkArrangement = Literal["not_required", "required", "preferred"]
EmploymentType = Literal["full_time", "part_time", "contract", "internship"]
LookbackWindow = Literal["24h", "7d", "14d", "30d", "90d", "custom"]


class PreferencesIn(BaseModel):
    job_titles: list[str] = Field(max_length=30)
    required_skills: list[str] = Field(max_length=50)
    min_experience_years: int | None = Field(default=None, ge=0, le=50)
    max_experience_years: int | None = Field(default=None, ge=0, le=50)
    countries: list[str] = Field(default_factory=list, max_length=50)
    cities: list[str] = Field(default_factory=list, max_length=100)
    remote_ok: bool = False
    hybrid_ok: bool = False
    onsite_ok: bool = False
    relocation_ok: bool = False
    visa_sponsorship: WorkArrangement | None = None
    min_salary: int | None = Field(default=None, ge=0)
    employment_type: EmploymentType | None = None
    max_posting_age_days: int | None = Field(default=None, ge=1, le=365)
    min_match_score: int | None = Field(default=None, ge=0, le=100)
    lookback_window: LookbackWindow | None = None
    lookback_from: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    lookback_to: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")

    @model_validator(mode="after")
    def validate_ranges(self) -> "PreferencesIn":
        if (
            self.min_experience_years is not None
            and self.max_experience_years is not None
            and self.min_experience_years > self.max_experience_years
        ):
            raise ValueError("min_experience_years cannot exceed max_experience_years")
        if self.lookback_window == "custom":
            if not self.lookback_from or not self.lookback_to:
                raise ValueError("custom lookback requires lookback_from and lookback_to")
            if self.lookback_from > self.lookback_to:
                raise ValueError("lookback_from must not be after lookback_to")
        return self


class PreferencesOut(PreferencesIn):
    user_id: str


def _to_in(prefs: JobPreferences) -> PreferencesIn:
    def split(value: str | None) -> list[str]:
        return [item.strip() for item in value.split(",")] if value else []

    return PreferencesIn(
        job_titles=split(prefs.job_titles),
        required_skills=split(prefs.required_skills),
        min_experience_years=prefs.min_experience_years,
        max_experience_years=prefs.max_experience_years,
        countries=split(prefs.countries),
        cities=split(prefs.cities),
        remote_ok=prefs.remote_ok,
        hybrid_ok=prefs.hybrid_ok,
        onsite_ok=prefs.onsite_ok,
        relocation_ok=prefs.relocation_ok,
        visa_sponsorship=prefs.visa_sponsorship,  # type: ignore[arg-type]
        min_salary=prefs.min_salary,
        employment_type=prefs.employment_type,  # type: ignore[arg-type]
        max_posting_age_days=prefs.max_posting_age_days,
        min_match_score=prefs.min_match_score,
        lookback_window=prefs.lookback_window,  # type: ignore[arg-type]
        lookback_from=prefs.lookback_from,
        lookback_to=prefs.lookback_to,
    )


def _apply(prefs: JobPreferences, payload: PreferencesIn) -> None:
    prefs.job_titles = ", ".join(payload.job_titles) or None
    prefs.required_skills = ", ".join(payload.required_skills) or None
    prefs.countries = ", ".join(payload.countries) or None
    prefs.cities = ", ".join(payload.cities) or None
    prefs.min_experience_years = payload.min_experience_years
    prefs.max_experience_years = payload.max_experience_years
    prefs.remote_ok = payload.remote_ok
    prefs.hybrid_ok = payload.hybrid_ok
    prefs.onsite_ok = payload.onsite_ok
    prefs.relocation_ok = payload.relocation_ok
    prefs.visa_sponsorship = payload.visa_sponsorship
    prefs.min_salary = payload.min_salary
    prefs.employment_type = payload.employment_type
    prefs.max_posting_age_days = payload.max_posting_age_days
    prefs.min_match_score = payload.min_match_score
    prefs.lookback_window = payload.lookback_window
    prefs.lookback_from = payload.lookback_from
    prefs.lookback_to = payload.lookback_to


def get_preferences_for_user(user_id: str) -> PreferencesIn | None:
    """Runtime accessor for discovery/matching services (never bake into code)."""
    with session_scope() as session:
        prefs = session.scalar(
            select(JobPreferences).where(JobPreferences.user_id == user_id)
        )
        return _to_in(prefs) if prefs else None


@router.get("", response_model=PreferencesOut)
def get_preferences(user: User = Depends(get_current_user)) -> PreferencesOut:
    with session_scope() as session:
        prefs = session.scalar(
            select(JobPreferences).where(JobPreferences.user_id == user.id)
        )
        if prefs is None:
            raise HTTPException(status_code=404, detail="Preferences not saved yet")
        result = _to_in(prefs).model_dump()
        result["user_id"] = str(prefs.user_id)
        return PreferencesOut.model_validate(result)


@router.put("", response_model=PreferencesOut)
def upsert_preferences(
    payload: PreferencesIn, user: User = Depends(get_current_user)
) -> PreferencesOut:
    with session_scope() as session:
        prefs = session.scalar(
            select(JobPreferences).where(JobPreferences.user_id == user.id)
        )
        if prefs is None:
            prefs = JobPreferences(user_id=user.id)
            session.add(prefs)
        _apply(prefs, payload)
        session.flush()
        result = _to_in(prefs).model_dump()
        result["user_id"] = str(prefs.user_id)
        return PreferencesOut.model_validate(result)
