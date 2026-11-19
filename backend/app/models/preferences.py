"""User job preferences: inputs for discovery and matching, editable at runtime."""

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin, UuidPkMixin


class JobPreferences(UuidPkMixin, TimestampMixin, Base):
    __tablename__ = "job_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    # Comma-separated lists are normalised by the API into rows below for
    # structured fields; free-form titles stay here.
    job_titles: Mapped[str | None] = mapped_column(Text, nullable=True)
    required_skills: Mapped[str | None] = mapped_column(Text, nullable=True)
    min_experience_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_experience_years: Mapped[int | None] = mapped_column(Integer, nullable=True)

    countries: Mapped[str | None] = mapped_column(Text, nullable=True)
    cities: Mapped[str | None] = mapped_column(Text, nullable=True)

    remote_ok: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    hybrid_ok: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    onsite_ok: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    relocation_ok: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    # None = no requirement; "required" = only sponsorship-enabled vacancies.
    visa_sponsorship: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # not_required|required|preferred

    min_salary: Mapped[int | None] = mapped_column(Integer, nullable=True)
    employment_type: Mapped[str | None] = mapped_column(
        String(30), nullable=True
    )  # full_time|part_time|contract|internship
    max_posting_age_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_match_score: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Historical discovery lookback window.
    lookback_window: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # 24h|7d|14d|30d|90d|custom
    lookback_from: Mapped[str | None] = mapped_column(
        String(10), nullable=True
    )  # ISO date, used when lookback_window=custom
    lookback_to: Mapped[str | None] = mapped_column(String(10), nullable=True)
