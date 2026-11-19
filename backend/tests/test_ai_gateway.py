"""AI gateway acceptance tests (issue #43) — mocked Anthropic client only."""

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import gateway
from app.ai.gateway import ModelTier, complete, estimate_cost_micro
from app.models.ai import AiCache, AiUsageLog

PASSWORD = "correct-horse-battery"
PROMPT = "Analyse this job description: <jd>{}</jd>"


@pytest.fixture(scope="session")
def app(engine):
    from fastapi.testclient import TestClient

    return TestClient(create_app := __import__("app.main", fromlist=["create_app"]).create_app())


@pytest.fixture(autouse=True)
def clean_ai_tables(db_session: Session) -> Iterator[None]:
    db_session.query(AiCache).delete()
    db_session.query(AiUsageLog).delete()
    db_session.flush()
    yield


class FakeCaller:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.responses: list[str] = []

    def create(self, model: str, max_tokens: int, prompt: str) -> tuple[str, int, int]:
        self.calls.append(prompt)
        text = self.responses.pop(0) if self.responses else f"reply-{len(self.calls)}"
        return text, 100, 50


@pytest.fixture
def fake_caller() -> FakeCaller:
    caller = FakeCaller()
    gateway.set_caller(caller)  # type: ignore[arg-type]
    yield caller
    gateway.set_caller(None)


def _settings(**overrides: object) -> None:
    """Override cached settings for the gateway within a test."""
    current = gateway.get_settings()
    for key, value in overrides.items():
        object.__setattr__(current, key, value)


def test_cache_hit_on_identical_input(fake_caller: FakeCaller, db_session: Session) -> None:
    first = complete("job_analysis", PROMPT.format("same"), session=db_session)
    assert first.status == "completed"

    second = complete("job_analysis", PROMPT.format("same"), session=db_session)
    assert second.status == "cache_hit"
    assert second.cache_hit is True
    assert second.text == first.text
    assert second.input_tokens == 0 and second.output_tokens == 0  # zero API tokens
    assert len(fake_caller.calls) == 1  # API called exactly once


def test_every_call_recorded_with_task_model_tokens_cost(
    fake_caller: FakeCaller, db_session: Session
) -> None:
    complete(
        "job_analysis", PROMPT.format("one"), model_tier=ModelTier.CAPABLE, session=db_session
    )
    row = db_session.scalar(select(AiUsageLog))
    assert row is not None
    assert row.task_type == "job_analysis"
    assert row.model.startswith("claude-sonnet")
    assert row.input_tokens == 100
    assert row.output_tokens == 50
    assert row.estimated_cost_micro > 0
    assert row.succeeded is True


def test_budget_exhausted_skips_non_critical(fake_caller: FakeCaller, db_session: Session) -> None:
    _settings(ai_daily_budget_micro=0)
    try:
        result = complete("job_analysis", PROMPT.format("two"), session=db_session)
        assert result.status == "skipped_budget"
        assert fake_caller.calls == []
        row = db_session.scalar(select(AiUsageLog))
        assert row is not None
        assert row.succeeded is False
        assert row.detail == "skipped_budget"
    finally:
        _settings(ai_daily_budget_micro=None)


def test_critical_call_bypasses_budget_gate(fake_caller: FakeCaller, db_session: Session) -> None:
    _settings(ai_daily_budget_micro=0)
    try:
        result = complete("sponsorship_analysis", PROMPT.format("x"), critical=True, session=db_session)
        assert result.status == "completed"
        assert len(fake_caller.calls) == 1
    finally:
        _settings(ai_daily_budget_micro=None)


def test_monthly_budget_enforced(fake_caller: FakeCaller, db_session: Session) -> None:
    db_session.add(
        AiUsageLog(
            user_id=None,
            task_type="other",
            model="claude-3-5-haiku-latest",
            input_tokens=0,
            output_tokens=0,
            estimated_cost_micro=9999,
            cache_hit=False,
            succeeded=True,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    _settings(ai_monthly_budget_micro=0)
    try:
        result = complete("job_analysis", PROMPT.format("y"), session=db_session)
        assert result.status == "skipped_budget"
    finally:
        _settings(ai_monthly_budget_micro=None)


def test_different_inputs_are_separate_cache_entries(
    fake_caller: FakeCaller, db_session: Session
) -> None:
    first = complete("job_analysis", PROMPT.format("a"), session=db_session)
    second = complete("job_analysis", PROMPT.format("b"), session=db_session)
    assert first.status == "completed"
    assert second.status == "completed"
    assert len(fake_caller.calls) == 2


def test_cheap_tier_uses_cheaper_model(fake_caller: FakeCaller, db_session: Session) -> None:
    result = complete("job_analysis", PROMPT.format("tier"), session=db_session)
    assert result.model is not None
    assert "haiku" in result.model


def test_cost_estimation_math() -> None:
    # haiku: 80 micro-USD/1K in, 400 out → (100*80 + 50*400)/1000 = 28 micro
    assert estimate_cost_micro("claude-3-5-haiku-latest", 100, 50) == 28
