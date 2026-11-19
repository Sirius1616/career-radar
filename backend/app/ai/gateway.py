"""Cost-controlled gateway for the Anthropic Claude API.

All AI calls go through complete(): model tiering, max-token limits,
content-hash caching, per-call usage metering with cost estimation, and
configurable daily/monthly budgets that skip non-critical calls when exceeded.
"""

import hashlib
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import session_scope
from app.models.ai import AiCache, AiUsageLog

# Micro-USD (1e-6 USD) per 1K tokens, keyed by model family. Conservative
# estimates; overridden per response when the API reports token usage.
PRICING_MICRO_PER_1K: dict[str, tuple[int, int]] = {
    "claude-3-5-haiku": (80, 400),
    "claude-sonnet": (300, 1500),
    "claude-opus": (1500, 7500),
}
DEFAULT_PRICING = (300, 1500)


class ModelTier:
    CHEAP = "cheap"
    CAPABLE = "capable"


def _model_for_tier(tier: str) -> str:
    settings = get_settings()
    if tier == ModelTier.CAPABLE:
        return settings.ai_capable_model
    return settings.ai_cheap_model


def _pricing_for(model: str) -> tuple[int, int]:
    for family, pricing in PRICING_MICRO_PER_1K.items():
        if model.startswith(family):
            return pricing
    return DEFAULT_PRICING


def estimate_cost_micro(model: str, input_tokens: int, output_tokens: int) -> int:
    input_price, output_price = _pricing_for(model)
    return (input_tokens * input_price + output_tokens * output_price) // 1000


@dataclass
class GatewayResult:
    status: str  # "completed" | "cache_hit" | "skipped_budget"
    text: str | None = None
    model: str | None = None
    cache_hit: bool = False
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_micro: int = 0


class AnthropicCaller:
    """Thin injectable wrapper so tests can mock the Anthropic SDK."""

    def __init__(self) -> None:
        import anthropic  # imported lazily; never required for tests

        settings = get_settings()
        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not configured")
        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    def create(self, model: str, max_tokens: int, prompt: str) -> tuple[str, int, int]:
        response = self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(
            block.text for block in response.content if getattr(block, "type", "") == "text"
        )
        usage = response.usage
        return text, usage.input_tokens, usage.output_tokens


_caller: AnthropicCaller | None = None


def get_caller() -> AnthropicCaller:
    global _caller
    if _caller is None:
        _caller = AnthropicCaller()
    return _caller


def set_caller(caller: AnthropicCaller | None) -> None:
    global _caller
    _caller = caller


def make_cache_key(task_type: str, model: str, max_tokens: int, prompt: str) -> str:
    material = f"{task_type}|{model}|{max_tokens}|{prompt}"
    return hashlib.sha256(material.encode()).hexdigest()


def _spend_micro(session: Session, since: datetime) -> int:
    total = session.scalar(
        select(func.coalesce(func.sum(AiUsageLog.estimated_cost_micro), 0)).where(
            AiUsageLog.created_at >= since, AiUsageLog.succeeded.is_(True)
        )
    )
    return int(total or 0)


def check_budget(session: Session, critical: bool) -> bool:
    """False when spend exceeds the configured budget for a non-critical call."""
    settings = get_settings()
    now = datetime.now(UTC)
    if not critical:
        daily_limit = settings.ai_daily_budget_micro
        if (
            daily_limit is not None
            and _spend_micro(
                session, now.replace(hour=0, minute=0, second=0, microsecond=0)
            )
            >= daily_limit
        ):
            return False
        monthly_limit = settings.ai_monthly_budget_micro
        if monthly_limit is not None:
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if _spend_micro(session, month_start) >= monthly_limit:
                return False
    return True


def complete(
    task_type: str,
    prompt: str,
    *,
    model_tier: str = ModelTier.CHEAP,
    max_tokens: int = 1024,
    critical: bool = False,
    user_id: uuid.UUID | None = None,
    use_cache: bool = True,
    session: Session | None = None,
) -> GatewayResult:
    model = _model_for_tier(model_tier)
    cache_key = make_cache_key(task_type, model, max_tokens, prompt)

    def log(
        db: Session,
        *,
        cache_hit: bool = False,
        succeeded: bool = True,
        input_tokens: int = 0,
        output_tokens: int = 0,
        detail: str | None = None,
    ) -> int:
        cost = estimate_cost_micro(model, input_tokens, output_tokens)
        db.add(
            AiUsageLog(
                user_id=user_id,
                task_type=task_type,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                estimated_cost_micro=cost,
                cache_hit=cache_hit,
                succeeded=succeeded,
                detail=detail,
            )
        )
        db.flush()
        return cost

    if session is not None:
        return _complete_with_session(
            session, task_type, prompt, model, max_tokens, critical, cache_key, use_cache, log
        )
    with session_scope() as owned:
        return _complete_with_session(
            owned, task_type, prompt, model, max_tokens, critical, cache_key, use_cache, log
        )


def _complete_with_session(
    db: Session,
    task_type: str,
    prompt: str,
    model: str,
    max_tokens: int,
    critical: bool,
    cache_key: str,
    use_cache: bool,
    log: Callable[..., int],
) -> GatewayResult:
    if use_cache:
        cached = db.scalar(select(AiCache).where(AiCache.cache_key == cache_key))
        if cached is not None:
            cost = log(db, cache_hit=True, succeeded=True)
            return GatewayResult(
                status="cache_hit",
                text=cached.response,
                model=model,
                cache_hit=True,
                estimated_cost_micro=cost,
            )

    if not check_budget(db, critical):
        log(db, succeeded=False, detail="skipped_budget")
        return GatewayResult(status="skipped_budget", model=model)

    text, input_tokens, output_tokens = get_caller().create(model, max_tokens, prompt)
    cost = log(
        db,
        succeeded=True,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
    if use_cache:
        db.add(AiCache(cache_key=cache_key, response=text))
    return GatewayResult(
        status="completed",
        text=text,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost_micro=cost,
    )
