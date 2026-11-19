"""Employer registry model. ATS providers are infrastructure, not employers."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin, UuidPkMixin


class Employer(UuidPkMixin, TimestampMixin, Base):
    __tablename__ = "employers"

    created_by: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    career_url: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_url: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    ats_provider: Mapped[str | None] = mapped_column(String(40), nullable=True)
    feed_endpoint: Mapped[str | None] = mapped_column(String(500), nullable=True)
    monitoring_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="active"
    )  # active|paused|unsupported|error
    detection_evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
