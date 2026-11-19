"""enable pgvector extension

Revision ID: 90d16f3c32c0
Revises: 
Create Date: 2026-11-19 15:50:30.176058

"""
from collections.abc import Sequence

from alembic import op

revision: str = '90d16f3c32c0'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS vector")
