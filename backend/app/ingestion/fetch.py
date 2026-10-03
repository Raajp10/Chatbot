"""Download a manifest source and decide whether it's a webpage or a PDF."""

from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from app.ingestion.models import SourceType

# pnw.edu serves a generic Purdue homepage (HTTP 200) to clients that don't look like a
# browser, so send ordinary browser headers. The parsers additionally validate that the body
# is really the requested page/PDF rather than trusting the status code alone.
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


class FetchError(Exception):
    """A source could not be downloaded, or the server returned something other than it."""


@dataclass(frozen=True)
class FetchedSource:
    url: str
    final_url: str
    content: bytes
    content_type: str
    source_type: SourceType


def fetch_source(url: str, client: httpx.Client | None = None, retries: int = 2) -> FetchedSource:
    owns_client = client is None
    client = client or httpx.Client(follow_redirects=True, timeout=30.0, headers=BROWSER_HEADERS)
    try:
        for attempt in range(retries + 1):
            try:
                response = client.get(url)
                response.raise_for_status()
                break
            except httpx.HTTPStatusError as exc:
                # 4xx won't fix itself on retry; 5xx might.
                if exc.response.status_code < 500 or attempt == retries:
                    raise FetchError(f"Failed to download {url}: {exc}") from exc
            except httpx.TransportError as exc:
                if attempt == retries:
                    raise FetchError(f"Failed to download {url}: {exc}") from exc
    finally:
        if owns_client:
            client.close()

    content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
    body = response.content
    if not body:
        raise FetchError(f"Downloaded {url} but the response body was empty")

    looks_like_pdf = body.lstrip()[:5] == b"%PDF-"
    expects_pdf = urlparse(url).path.lower().endswith(".pdf")
    if looks_like_pdf or content_type == "application/pdf":
        if not looks_like_pdf:
            raise FetchError(f"{url} claims to be a PDF but the body is not a PDF file")
        source_type: SourceType = "pdf"
    elif expects_pdf:
        raise FetchError(
            f"{url} should be a PDF but the server returned {content_type or 'unknown content'} "
            "(possibly a block/redirect page)"
        )
    elif content_type in ("text/html", "application/xhtml+xml") or body.lstrip()[:1] == b"<":
        source_type = "webpage"
    else:
        raise FetchError(f"Unsupported content type {content_type!r} for {url}")

    return FetchedSource(
        url=url,
        final_url=str(response.url),
        content=body,
        content_type=content_type,
        source_type=source_type,
    )
