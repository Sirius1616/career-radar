"""HTTP retrieval helpers for employer pages.

Treats all retrieved content as untrusted data. Enforces URL safety (no
private/internal hosts) and robots.txt compliance for website access.
Public ATS feed APIs are used directly where the employer hosts them.
"""

import hashlib
import ipaddress
import re
import socket
import time
import urllib.robotparser
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlsplit

import httpx

USER_AGENT = "CareerRadar/0.1 (+https://github.com/Sirius1616/career-radar)"
MAX_PAGE_BYTES = 2_000_000
TIMEOUT_SECONDS = 15.0


class FetchError(Exception):
    """Raised when a page cannot be retrieved safely or at all."""


@dataclass(frozen=True)
class Page:
    url: str
    content: str
    title: str | None
    final_url: str = ""
    fetched_at: datetime = None  # type: ignore[assignment]


def validate_public_url(raw_url: str) -> str:
    """Return the normalised URL, raising FetchError for non-public targets."""
    try:
        parts = urlsplit(raw_url)
    except ValueError as exc:
        raise FetchError(f"Invalid URL: {raw_url}") from exc
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise FetchError("URL must be a valid http(s) address")
    try:
        infos = socket.getaddrinfo(parts.hostname, None)
    except socket.gaierror as exc:
        raise FetchError(f"Could not resolve host: {parts.hostname}") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise FetchError("Refusing to fetch non-public addresses")
    return raw_url


def robots_allows(url: str) -> bool:
    """Check robots.txt for the URL path. A missing robots.txt allows access."""
    parts = urlsplit(url)
    robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
    parser = urllib.robotparser.RobotFileParser()
    try:
        response = httpx.get(
            robots_url,
            timeout=TIMEOUT_SECONDS,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        )
        if response.status_code in (401, 403):
            return False
        parser.parse(response.text.splitlines())
    except httpx.HTTPError:
        return True
    return parser.can_fetch(USER_AGENT, url)


def extract_title(html: str) -> str | None:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    if not match:
        return None
    title = re.sub(r"\s+", " ", match.group(1)).strip()
    return title[:200] or None


def fetch_page(url: str) -> Page:
    """Fetch a public page with size and content-type limits."""
    validate_public_url(url)
    if not robots_allows(url):
        raise FetchError("robots.txt disallows fetching this page")
    try:
        response = httpx.get(
            url,
            timeout=TIMEOUT_SECONDS,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        )
    except httpx.HTTPError as exc:
        raise FetchError(f"Career page unreachable: {exc.__class__.__name__}") from exc
    if response.status_code != 200:
        raise FetchError(f"Career page returned HTTP {response.status_code}")
    content_type = response.headers.get("content-type", "")
    if content_type and "text/html" not in content_type and "text/plain" not in content_type:
        raise FetchError(f"Unsupported content type: {content_type.split(';')[0]}")
    content = response.text[:MAX_PAGE_BYTES]
    return Page(
        url=url,
        content=content,
        title=extract_title(content),
        final_url=str(response.url),
        fetched_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# Job-content retrieval (issue #42)
#
# HTTP-first: selectolax extraction from statically served HTML. A renderer
# (browser automation) is only invoked when static extraction is insufficient,
# and it must be supplied by the caller — Playwright runs in the worker process
# only, never in the API process. The renderer decision criteria are:
#   * static text shorter than MIN_STATIC_TEXT_CHARS, or
#   * content-type/text present but main content markers absent.
# ---------------------------------------------------------------------------

MIN_STATIC_TEXT_CHARS = 200
CACHE_TTL_SECONDS = 3600

_document_cache: dict[str, tuple["RetrievedDocument", float]] = {}


@dataclass(frozen=True)
class RetrievedDocument:
    url: str
    final_url: str
    text: str
    raw_html: str
    source: str  # "static" | "browser"
    fetched_at: datetime
    sufficient: bool


def _cache_key(url: str) -> str:
    return hashlib.sha256(url.strip().lower().encode()).hexdigest()


def _cache_get(url: str) -> RetrievedDocument | None:
    entry = _document_cache.get(_cache_key(url))
    if entry is None:
        return None
    document, stored_at = entry
    if time.time() - stored_at > CACHE_TTL_SECONDS:
        _document_cache.pop(_cache_key(url), None)
        return None
    return document


def _cache_put(document: RetrievedDocument) -> None:
    _document_cache[_cache_key(document.url)] = (document, time.time())


def extract_text(html: str) -> str:
    from selectolax.lexbor import LexborHTMLParser as HTMLParser  # type: ignore[attr-defined]

    tree = HTMLParser(html)
    for node in tree.css("script, style, noscript"):
        node.decompose()
    text = tree.text(separator="\n", strip=True) if tree.body else ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)[:MAX_PAGE_BYTES]


def fetch_job_content(
    url: str,
    render: Callable[[str], str] | None = None,
    use_cache: bool = True,
) -> RetrievedDocument:
    """Retrieve a job page safely; browser fallback only when necessary.

    All returned content is untrusted data: it is never executed, never
    followed as instructions, and only ever used for parsing/analysis.
    """
    if use_cache:
        cached = _cache_get(url)
        if cached is not None:
            return cached
    page = fetch_page(url)
    text = extract_text(page.content)
    sufficient = len(text) >= MIN_STATIC_TEXT_CHARS
    if not sufficient and render is not None:
        rendered_html = render(url)  # single fallback attempt
        text = extract_text(rendered_html)
        sufficient = len(text) >= MIN_STATIC_TEXT_CHARS
        document = RetrievedDocument(
            url=url,
            final_url=page.final_url,
            text=text,
            raw_html=rendered_html[:MAX_PAGE_BYTES],
            source="browser",
            fetched_at=page.fetched_at,
            sufficient=sufficient,
        )
    else:
        document = RetrievedDocument(
            url=url,
            final_url=page.final_url,
            text=text,
            raw_html=page.content[:MAX_PAGE_BYTES],
            source="static",
            fetched_at=page.fetched_at,
            sufficient=sufficient,
        )
    if use_cache:
        _cache_put(document)
    if not sufficient:
        raise FetchError(
            f"Insufficient content from {url} (source={document.source})"
        )
    return document
