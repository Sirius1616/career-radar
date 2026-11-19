"""ATS provider detection from career-page URLs.

ATS providers are infrastructure used by employers; they are never treated as
employers themselves. Detection here is URL-pattern based; HTTP probing of the
career page is added by the follow-up detection issue (#36).
"""

import re
from dataclasses import dataclass

UNKNOWN = "NOT_DETECTED"
NOT_DETECTED = UNKNOWN


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
    (
        "WORKDAY",
        re.compile(
            r"(?P<host>[a-z0-9-]+)\.wd[0-9]+\.myworkdayjobs\.com/(?P<token>[a-zA-Z0-9_-]+)", re.I
        ),
        "https://{host}.wd1.myworkdayjobs.com/wday/cxs/{tenant}/{token}/jobs",
    ),
]


def detect_ats_provider(career_url: str) -> DetectionResult:
    for provider, pattern, feed_template in _PATTERNS:
        match = pattern.search(career_url)
        if match:
            token = match.group("token")
            groups = match.groupdict()
            feed = (
                feed_template.format(token=token, host=groups.get("host"), tenant=groups.get("host"))
                if "{host}" in feed_template
                else feed_template.format(token=token)
            )
            return DetectionResult(
                provider=provider,
                feed_endpoint=feed,
                evidence=f"career URL matched {provider} board pattern: {career_url}",
            )
    return _detect_from_html(career_url, None)


HTML_MARKERS: list[tuple[str, re.Pattern[str]]] = [
    ("GREENHOUSE", re.compile(r"(?:boards\.greenhouse\.io|greenhouse\.io/embed/job_board)", re.I)),
    ("LEVER", re.compile(r"(?:jobs\.lever\.co|lever\.co/jobs)", re.I)),
    ("ASHBY", re.compile(r"jobs\.ashbyhq\.com", re.I)),
    ("WORKABLE", re.compile(r"apply\.workable\.com", re.I)),
    ("RECRUITEE", re.compile(r"[a-z0-9-]+\.recruitee\.com", re.I)),
    ("PERSONIO", re.compile(r"[a-z0-9-]+\.jobs\.personio\.(?:de|com)", re.I)),
    ("TEAMTAILOR", re.compile(r"[a-z0-9-]+\.teamtailor\.com", re.I)),
    ("SMARTRECRUITERS", re.compile(r"smartrecruiters", re.I)),
    ("WORKDAY", re.compile(r"myworkdayjobs\.com|myworkdaysite\.com", re.I)),
]


def _detect_from_html(career_url: str, html: str | None) -> DetectionResult:
    if html:
        for provider, marker in HTML_MARKERS:
            if marker.search(html):
                return DetectionResult(
                    provider=provider,
                    feed_endpoint=None,
                    evidence=f"career page HTML contains {provider} marker: {career_url}",
                )
    return DetectionResult(
        provider=UNKNOWN,
        feed_endpoint=None,
        evidence=f"no supported ATS pattern matched: {career_url}",
    )


def detect_from_page(career_url: str, html: str) -> DetectionResult:
    """Second-stage detection: probe fetched career-page HTML for ATS markers."""
    direct = detect_ats_provider(career_url)
    if direct.provider != UNKNOWN:
        return direct
    return _detect_from_html(career_url, html)
