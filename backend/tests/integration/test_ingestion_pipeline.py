"""End-to-end ingestion into a real PostgreSQL/pgvector database (isolated schema per test).

Network and Gemini are replaced by in-memory fakes so these tests are fast and free; they
are skipped when the database isn't running (`docker compose up -d db`).
"""

import pytest

from app.config import EMBEDDING_DIMENSIONS
from app.ingestion.fetch import FetchedSource, FetchError
from app.ingestion.models import SourceEntry
from app.ingestion.pipeline import ingest_all
from app.retrieval import query
from tests.conftest import fake_vector, make_pdf
from tests.unit.test_parsers import POLICY_HTML
from tests.unit.test_parsers import URL as HTML_URL

PDF_URL = "https://www.pnw.edu/example/behavior.pdf"
PDF_PAGES = [
    ["Classroom Behavior Policy", "Preamble",
     "Disruptive behavior in the classroom will not be tolerated by the university."],
    ["Counseling Center", "The Counseling Center helps students experiencing emotional concerns."],
]

ENTRIES = [
    SourceEntry(url=HTML_URL, title="Example Policy", id="example-policy",
                category="attendance", context={"campus": "both"}),
    SourceEntry(url=PDF_URL, title="Classroom Behavior Policy", id="behavior-policy"),
]


class FakeWeb:
    def __init__(self) -> None:
        self.pages = {HTML_URL: POLICY_HTML.encode(), PDF_URL: make_pdf(PDF_PAGES)}

    def __call__(self, url: str) -> FetchedSource:
        if url not in self.pages:
            raise FetchError(f"Failed to download {url}: 404")
        kind = "pdf" if url.endswith(".pdf") else "webpage"
        return FetchedSource(url, url, self.pages[url], "", kind)


def _counts(conn):
    return conn.execute(
        "SELECT (SELECT count(*) FROM documents), (SELECT count(*) FROM chunks)"
    ).fetchone()


def _ingest(conn, embedder, web=None, **kwargs):
    return ingest_all(conn, ENTRIES, fetch=web or FakeWeb(), embed=embedder,
                      log=lambda _: None, **kwargs)


def test_documents_chunks_and_embeddings_are_stored(db_conn, fake_embedder):
    results = _ingest(db_conn, fake_embedder)
    assert [r.status for r in results] == ["ingested", "ingested"]

    documents, chunks = _counts(db_conn)
    assert documents == 2
    assert chunks == sum(r.chunk_count for r in results) > 0

    rows = db_conn.execute(
        """
        SELECT d.document_key, d.source_type, c.chunk_index, c.content, c.page_number,
               c.metadata, vector_dims(c.embedding)
        FROM chunks c JOIN documents d ON d.id = c.document_id
        ORDER BY d.document_key, c.chunk_index
        """
    ).fetchall()
    for key, source_type, index, content, page, metadata, dims in rows:
        assert content.strip()
        assert dims == EMBEDDING_DIMENSIONS
        assert metadata["documentId"] == key
        assert metadata["chunkIndex"] == index
        assert metadata["sourceUrl"] in (HTML_URL, PDF_URL)
        assert metadata["title"]
        assert (page is not None) == (source_type == "pdf")
    html_meta = next(m for k, *_, m, _ in rows if k == "example-policy")
    assert html_meta["campus"] == "both" and html_meta["category"] == "attendance"


def test_rerunning_ingestion_does_not_duplicate(db_conn, fake_embedder):
    _ingest(db_conn, fake_embedder)
    first = _counts(db_conn)
    embedded_once = fake_embedder.texts_embedded

    results = _ingest(db_conn, fake_embedder)
    assert [r.status for r in results] == ["unchanged", "unchanged"]
    assert _counts(db_conn) == first
    assert fake_embedder.texts_embedded == embedded_once  # no new embedding API calls

    results = _ingest(db_conn, fake_embedder, force=True)
    assert [r.status for r in results] == ["ingested", "ingested"]
    assert _counts(db_conn) == first


def test_changed_source_replaces_its_chunks(db_conn, fake_embedder):
    web = FakeWeb()
    _ingest(db_conn, fake_embedder, web)
    web.pages[PDF_URL] = make_pdf([["Classroom Behavior Policy", "Preamble",
                                    "Rewritten policy text about respectful classroom conduct."]])
    results = _ingest(db_conn, fake_embedder, web)
    assert [r.status for r in results] == ["unchanged", "ingested"]

    contents = [row[0] for row in db_conn.execute(
        "SELECT c.content FROM chunks c JOIN documents d ON d.id = c.document_id "
        "WHERE d.document_key = 'behavior-policy'"
    ).fetchall()]
    assert any("Rewritten policy text" in c for c in contents)
    assert not any("Counseling Center" in c for c in contents)


def test_failed_source_is_reported_and_keeps_previous_version(db_conn, fake_embedder):
    web = FakeWeb()
    _ingest(db_conn, fake_embedder, web)
    before = _counts(db_conn)

    del web.pages[PDF_URL]
    results = _ingest(db_conn, fake_embedder, web, force=True)
    assert [r.status for r in results] == ["ingested", "failed"]
    assert "404" in results[1].error
    assert _counts(db_conn) == before


def test_similarity_search_returns_the_relevant_document(db_conn, fake_embedder):
    _ingest(db_conn, fake_embedder)
    hits = query(fake_vector("disruptive behavior classroom tolerated"), k=1, conn=db_conn)
    assert hits[0]["url"] == PDF_URL
    assert hits[0]["title"] == "Classroom Behavior Policy"
    assert hits[0]["pageNumber"] == 1

    hits = query(fake_vector("immediate family five days grief"), k=1, conn=db_conn)
    assert hits[0]["url"] == HTML_URL
    assert "Up to five days for immediate family." in hits[0]["content"]


@pytest.mark.parametrize("where,expected", [({"campus": "both"}, {HTML_URL}), ({}, {HTML_URL, PDF_URL})])
def test_search_metadata_filter(db_conn, fake_embedder, where, expected):
    _ingest(db_conn, fake_embedder)
    hits = query(fake_vector("policy"), where=where, k=50, conn=db_conn)
    assert {h["url"] for h in hits} == expected
