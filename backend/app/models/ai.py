"""AI usage metering and content-hash cache tables."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin, UuidPkMixin


class AiUsageLog(UuidPkMixin, TimestampMixin, Base):
    __tablename__ = "ai_usage_logs"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    task_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(60), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    estimated_cost_micro: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    cache_hit: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    succeeded: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)


class AiCache(UuidPkMixin, Base):
    __tablename__ = "ai_cache"

    cache_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    response: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
