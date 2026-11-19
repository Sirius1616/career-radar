"""Discovered job postings, deduplicated per (employer, normalised source URL)."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin, UuidPkMixin


class Job(UuidPkMixin, TimestampMixin, Base):
    __tablename__ = "jobs"

    employer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("employers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    source_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)

    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="new"
    )  # new|analysed|closed|unavailable

    location: Mapped[str | None] = mapped_column(String(300), nullable=True)
    department: Mapped[str | None] = mapped_column(String(300), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    description_format: Mapped[str] = mapped_column(String(10), nullable=False, server_default="text")
    feed_metadata: Mapped[str] = mapped_column(Text, nullable=False)
