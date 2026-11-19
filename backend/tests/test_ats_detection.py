"""ATS provider detection acceptance tests (issue #36)."""

import pytest

from app.providers.detection import NOT_DETECTED, detect_ats_provider, detect_from_page

# provider -> (career URL, expected public feed endpoint)
URL_FIXTURES = {
    "GREENHOUSE": (
        "https://boards.greenhouse.io/stripe",
        "https://boards-api.greenhouse.io/v1/boards/stripe/jobs?content=true",
    ),
    "GREENHOUSE_EMBED": (
        "https://boards.greenhouse.io/embed/job_board?for=plaid",
        "https://boards-api.greenhouse.io/v1/boards/plaid/jobs?content=true",
    ),
    "LEVER": (
        "https://jobs.lever.co/netflix",
        "https://api.lever.co/v0/postings/netflix?mode=json",
    ),
    "ASHBY": (
        "https://jobs.ashbyhq.com/ramp",
        "https://api.ashbyhq.com/posting-api/job-list/ramp?includeCompensation=true",
    ),
    "WORKABLE": (
        "https://apply.workable.com/canonical",
        "https://apply.workable.com/api/v1/widget/accounts/canonical?details=true",
    ),
    "RECRUITEE": (
        "https://justwatch.recruitee.com",
        "https://justwatch.recruitee.com/api/offers/",
    ),
    "PERSONIO": (
        "https://eu-recruit.jobs.personio.de",
        "https://eu-recruit.jobs.personio.de/xml",
    ),
    "TEAMTAILOR": (
        "https://kry.teamtailor.com",
        "https://kry.teamtailor.com/jobs.json",
    ),
    "SMARTRECRUITERS": (
        "https://jobs.smartrecruiters.com/Visa",
        "https://api.smartrecruiters.com/v1/companies/Visa/postings",
    ),
    "WORKDAY": (
        "https://nutanix.wd1.myworkdayjobs.com/NutanixCareers",
        "https://nutanix.wd1.myworkdayjobs.com/wday/cxs/nutanix/NutanixCareers/jobs",
    ),
}


@pytest.mark.parametrize("provider", sorted(URL_FIXTURES))
def test_detection_by_url(provider: str) -> None:
    career_url, expected_feed = URL_FIXTURES[provider]
    result = detect_ats_provider(career_url)
    assert result.provider == provider.replace("_EMBED", "")
    assert result.feed_endpoint == expected_feed
    assert career_url in result.evidence


def test_unknown_url_returns_not_detected_without_error() -> None:
    result = detect_ats_provider("https://careers.smallcompany.example")
    assert result.provider == NOT_DETECTED
    assert result.feed_endpoint is None
    assert result.evidence


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        ("<script src='https://boards.greenhouse.io/embed/job_board?for=acme'></script>", "GREENHOUSE"),
        ("<a href='https://jobs.lever.co/apply'>Apply</a>", "LEVER"),
        ("<div data-ats='https://jobs.ashbyhq.com/acme'>", "ASHBY"),
        ("<link rel='alternate' href='https://acme.teamtailor.com/jobs.json'>", "TEAMTAILOR"),
        ("<div id='smartRecruitersWidget'>", "SMARTRECRUITERS"),
    ],
)
def test_detection_from_page_html_markers(html: str, expected: str) -> None:
    result = detect_from_page("https://careers.unknown.example", html)
    assert result.provider == expected
    assert "HTML contains" in result.evidence


def test_detect_from_page_prefers_url_signature() -> None:
    result = detect_from_page(
        "https://jobs.lever.co/acme", "<script src='https://boards.greenhouse.io/x'></script>"
    )
    assert result.provider == "LEVER"
    assert result.feed_endpoint is not None


def test_detect_from_page_no_match() -> None:
    result = detect_from_page("https://careers.unknown.example", "<html>jobs here</html>")
    assert result.provider == NOT_DETECTED
