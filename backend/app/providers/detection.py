"""ATS provider detection from career-page URLs.

ATS providers are infrastructure used by employers; they are never treated as
employers themselves. Detection here is URL-pattern based; HTTP probing of the
career page is added by the follow-up detection issue (#36).
"""

import re
from dataclasses import dataclass

UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class DetectionResult:
    provider: str
    feed_endpoint: str | None
    evidence: str


_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    (
        "GREENHOUSE",
        re.compile(
            r"boards\.greenhouse\.io/(?:embed/job_board\?for=)?(?P<token>[a-z0-9_-]+)", re.I
        ),
        "https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true",
    ),
    (
        "LEVER",
        re.compile(r"jobs\.lever\.co/(?P<token>[a-z0-9_-]+)", re.I),
        "https://api.lever.co/v0/postings/{token}?mode=json",
    ),
    (
        "ASHBY",
        re.compile(r"jobs\.ashbyhq\.com/(?P<token>[a-z0-9_.-]+)", re.I),
        "https://api.ashbyhq.com/posting-api/job-list/{token}?includeCompensation=true",
    ),
    (
        "WORKABLE",
        re.compile(r"apply\.workable\.com/(?P<token>[a-z0-9_-]+)", re.I),
        "https://apply.workable.com/api/v1/widget/accounts/{token}?details=true",
    ),
    (
        "RECRUITEE",
        re.compile(r"(?P<token>[a-z0-9_-]+)\.recruitee\.com", re.I),
        "https://{token}.recruitee.com/api/offers/",
    ),
    (
        "PERSONIO",
        re.compile(r"(?P<token>[a-z0-9_-]+)\.jobs\.personio\.(?:de|com)", re.I),
        "https://{token}.jobs.personio.de/xml",
    ),
    (
        "TEAMTAILOR",
        re.compile(r"(?P<token>[a-z0-9_-]+)\.teamtailor\.com", re.I),
        "https://{token}.teamtailor.com/jobs.json",
    ),
    (
        "SMARTRECRUITERS",
        re.compile(r"(?:jobs|careers)\.smartrecruiters\.com/(?P<token>[A-Za-z0-9_-]+)", re.I),
        "https://api.smartrecruiters.com/v1/companies/{token}/postings",
    ),
]


def detect_ats_provider(career_url: str) -> DetectionResult:
    for provider, pattern, feed_template in _PATTERNS:
        match = pattern.search(career_url)
        if match:
            token = match.group("token")
            feed = feed_template.format(token=token)
            return DetectionResult(
                provider=provider,
                feed_endpoint=feed,
                evidence=f"career URL matched {provider} board pattern: {career_url}",
            )
    return DetectionResult(
        provider=UNKNOWN,
        feed_endpoint=None,
        evidence=f"no supported ATS pattern matched: {career_url}",
    )
