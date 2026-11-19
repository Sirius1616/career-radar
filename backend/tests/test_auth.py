"""Authentication acceptance tests (issue #29)."""

from collections.abc import Iterator
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import create_app
from app.models.user import User

PASSWORD = "correct-horse-battery"


@pytest.fixture(scope="session")
def app(engine) -> Iterator[TestClient]:
    client = TestClient(create_app())
    yield client


def _register(client: TestClient, email: str) -> dict[str, str]:
    resp = client.post("/auth/register", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_register_login_flow(app, db_session) -> None:
    headers = _register(app, "alice@example.com")
    user = db_session.scalar(select(User).where(User.email == "alice@example.com"))
    assert user is not None
    assert user.password_hash.startswith("$2b$")
    assert PASSWORD not in user.password_hash

    login = app.post("/auth/login", json={"email": "alice@example.com", "password": PASSWORD})
    assert login.status_code == 200
    assert login.json()["token_type"] == "bearer"

    me = app.get("/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == "alice@example.com"


def test_login_with_wrong_password_rejected(app) -> None:
    _register(app, "bob@example.com")
    resp = app.post("/auth/login", json={"email": "bob@example.com", "password": "wrong-password"})
    assert resp.status_code == 401


def test_register_duplicate_email_conflict(app) -> None:
    _register(app, "carol@example.com")
    resp = app.post("/auth/register", json={"email": "carol@example.com", "password": PASSWORD})
    assert resp.status_code == 409


def test_endpoints_require_token(app) -> None:
    resp = app.get("/auth/me")
    assert resp.status_code == 401


def test_invalid_token_rejected(app) -> None:
    resp = app.get("/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert resp.status_code == 401


def test_users_are_isolated(app, db_session) -> None:
    _register(app, "dave@example.com")
    headers = _register(app, "eve@example.com")
    dave = db_session.scalar(select(User).where(User.email == "dave@example.com"))
    # /auth/me only ever returns the token's own user.
    me = app.get("/auth/me", headers=headers)
    assert me.json()["id"] != str(dave.id)


def test_get_current_user_dependency_returns_owned_user(app, db_session) -> None:
    headers = _register(app, "frank@example.com")
    me = app.get("/auth/me", headers=headers)
    assert me.status_code == 200
    # Confirm the dependency resolves the persisted user row.
    user = db_session.get(User, UUID(me.json()["id"]))
    assert user is not None
    assert user.email == "frank@example.com"
