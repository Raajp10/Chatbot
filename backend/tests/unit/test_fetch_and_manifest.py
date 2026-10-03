import json

import httpx
import pytest

from app.ingestion.fetch import FetchError, fetch_source
from app.ingestion.models import load_manifest
from app.ingestion.run import DEFAULT_MANIFEST
from tests.conftest import make_pdf


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)


def test_detects_webpage_and_pdf():
    pdf = make_pdf([["Hello"]])

    def handler(request):
        if request.url.path.endswith(".pdf"):
            return httpx.Response(200, content=pdf, headers={"content-type": "application/pdf"})
        return httpx.Response(200, text="<html><body>x</body></html>",
                              headers={"content-type": "text/html; charset=utf-8"})

    with _client(handler) as client:
        assert fetch_source("https://x.edu/page/", client).source_type == "webpage"
        assert fetch_source("https://x.edu/doc.pdf", client).source_type == "pdf"


def test_html_served_for_a_pdf_url_is_an_error():
    # pnw.edu answers non-browser clients with a 200 HTML homepage instead of the PDF.
    html = httpx.Response(200, text="<html>home</html>", headers={"content-type": "text/html"})
    with _client(lambda r: html) as client, pytest.raises(FetchError, match="should be a PDF"):
        fetch_source("https://x.edu/policy.pdf", client)


def test_http_errors_are_not_ignored():
    with _client(lambda r: httpx.Response(404)) as client, pytest.raises(FetchError, match="404"):
        fetch_source("https://x.edu/missing/", client)


def test_server_errors_are_retried():
    attempts = []

    def handler(request):
        attempts.append(1)
        if len(attempts) < 3:
            return httpx.Response(503)
        return httpx.Response(200, text="<html>ok</html>", headers={"content-type": "text/html"})

    with _client(handler) as client:
        assert fetch_source("https://x.edu/flaky/", client, retries=2).source_type == "webpage"
    assert len(attempts) == 3


def test_project_manifest_lists_the_three_required_sources():
    entries = load_manifest(DEFAULT_MANIFEST)
    assert len(entries) >= 3
    assert {e.id for e in entries} >= {
        "student-absence-policy", "grade-appeal-policy", "classroom-behavior-policy",
    }
    assert any(e.url.endswith(".pdf") for e in entries)


def test_manifest_requires_url_and_title_and_unique_ids(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps([{"url": "https://x.edu/a"}]))
    with pytest.raises(ValueError, match="title"):
        load_manifest(bad)
    dupes = tmp_path / "dupes.json"
    dupes.write_text(json.dumps([{"id": "a", "url": "https://x.edu/1", "title": "A"},
                                 {"id": "a", "url": "https://x.edu/2", "title": "B"}]))
    with pytest.raises(ValueError, match="Duplicate"):
        load_manifest(dupes)
