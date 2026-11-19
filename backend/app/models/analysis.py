"""Structured job analysis output, provenance separated from AI interpretation."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin, UuidPkMixin


class JobAnalysis(UuidPkMixin, TimestampMixin, Base):
    __tablename__ = "job_analyses"

    job_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # Deterministic facts extracted by Python (regex/feed metadata) with spans.
    verified_fields: Mapped[str] = mapped_column(Text, nullable=False, server_default="{}")
    # Structured AI interpretation, always flagged ai_derived at the top level.
    structured_analysis: Mapped[str] = mapped_column(Text, nullable=False)
    ai_model: Mapped[str | None] = mapped_column(String(60), nullable=True)
    escalations: Mapped[int] = mapped_column(nullable=False, server_default="0")
    analysis_failed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    analysed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
