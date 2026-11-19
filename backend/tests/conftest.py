"""Test fixtures: isolated database per session, transactional rollback per test."""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Connection, Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

TEST_DATABASE_NAME = "career_radar_test"
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://career_radar:career_radar@localhost:5438/career_radar_test",
)
ADMIN_URL = TEST_DATABASE_URL.rsplit("/", 1)[0] + "/postgres"
MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


@pytest.fixture(scope="session")
def database_url() -> str:
    return TEST_DATABASE_URL


def _terminate_connections(admin_conn, name: str) -> None:
    admin_conn.execute(
        text(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = :name AND pid <> pg_backend_pid()"
        ),
        {"name": name},
    )


@pytest.fixture(scope="session")
def engine(database_url: str) -> Iterator[Engine]:
    admin = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        _terminate_connections(conn, TEST_DATABASE_NAME)
        conn.execute(
            text(f"DROP DATABASE IF EXISTS {TEST_DATABASE_NAME} WITH (FORCE)")
        )
        conn.execute(text(f"CREATE DATABASE {TEST_DATABASE_NAME}"))
    admin.dispose()

    # Re-read settings/env now that the test URL is set; drop any cached engine
    # created earlier in the process (e.g. by module-level app creation).
    os.environ["DATABASE_URL"] = database_url

    from app.config import get_settings

    get_settings.cache_clear()
    import app.db as app_db

    app_db._engine = None

    # Run real migrations against the fresh test database.
    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    command.upgrade(alembic_cfg, "head")

    engine = create_engine(database_url)
    yield engine
    with admin.connect() as conn:
        _terminate_connections(conn, TEST_DATABASE_NAME)
        conn.execute(
            text(f"DROP DATABASE IF EXISTS {TEST_DATABASE_NAME} WITH (FORCE)")
        )
    admin.dispose()
    engine.dispose()


_session_factory = sessionmaker(expire_on_commit=False)


@pytest.fixture
def db_session(engine: Engine) -> Iterator[Session]:
    """Session bound to an outer transaction that is always rolled back."""
    connection: Connection = engine.connect()
    transaction = connection.begin()
    session = _session_factory(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
