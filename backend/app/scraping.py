"""HTTP retrieval helpers for employer pages.

Treats all retrieved content as untrusted data. Enforces URL safety (no
private/internal hosts) and robots.txt compliance for website access.
Public ATS feed APIs are used directly where the employer hosts them.
"""

import ipaddress
import re
import socket
import urllib.robotparser
from dataclasses import dataclass
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
    return Page(url=str(response.url), content=content, title=extract_title(content))
