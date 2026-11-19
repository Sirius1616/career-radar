"""Database foundation acceptance tests (issue #28)."""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.testing import eq_

from app.db import Base, TimestampMixin, UuidPkMixin


@pytest.fixture(scope="session", autouse=True)
def sample_table(engine) -> None:
    from app.db import Base  # noqa: F401 - models register on Base

    SampleRecord.__table__.create(engine, checkfirst=True)


class SampleRecord(UuidPkMixin, TimestampMixin, Base):
    __tablename__ = "sample_records"

    name: Mapped[str] = mapped_column(nullable=False)


def test_tables_created_with_conventions(engine) -> None:
    with engine.connect() as conn:
        pk = conn.execute(
            text(
                "SELECT constraint_name FROM information_schema.table_constraints "
                "WHERE table_name='sample_records' AND constraint_type='PRIMARY KEY'"
            )
        ).scalar()
        eq_(pk, "pk_sample_records")


def test_pgvector_extension_enabled(engine) -> None:
    with engine.connect() as conn:
        ext = conn.execute(
            text("SELECT extname FROM pg_extension WHERE extname='vector'")
        ).scalar()
        eq_(ext, "vector")


def test_record_persists_with_defaults_and_rolls_back(db_session) -> None:
    record = SampleRecord(name="alpha")
    db_session.add(record)
    db_session.flush()
    assert record.id == uuid.UUID(str(record.id))
    assert record.created_at is not None
    assert record.updated_at is not None


def test_transactional_rollback_isolation(db_session) -> None:
    count = db_session.query(SampleRecord).count()
    eq_(count, 0)


def test_migrations_applied_schema_version(engine) -> None:
    with engine.connect() as conn:
        version = conn.execute(text("SELECT COUNT(*) FROM alembic_version")).scalar()
        eq_(version, 1)
