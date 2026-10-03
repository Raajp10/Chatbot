"""Shared test fixtures: synthetic PDFs, a fake (offline) embedder, and an isolated DB schema."""

import hashlib
import math
import re
import uuid

import pytest

from app.config import EMBEDDING_DIMENSIONS, ServiceUnavailableError


def make_pdf(pages: list[list[str]]) -> bytes:
    """Build a minimal valid PDF with one Helvetica text line per string, one page per list."""
    objects: list[bytes] = []
    n_pages = len(pages)
    page_ids = [4 + 2 * i for i in range(n_pages)]
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>".encode())
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    for i, lines in enumerate(pages):
        escaped = [line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") for line in lines]
        ops = ["BT", "/F1 11 Tf", "14 TL", "50 750 Td"]
        ops += [f"({line}) Tj T*" for line in escaped]
        ops.append("ET")
        stream = "\n".join(ops).encode("latin-1")
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {page_ids[i] + 1} 0 R >>".encode()
        )
        objects.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


def fake_vector(text: str) -> list[float]:
    """Deterministic bag-of-words embedding: texts sharing words are close in cosine distance."""
    vector = [0.0] * EMBEDDING_DIMENSIONS
    for word in re.findall(r"[a-z]{3,}", text.lower()):
        bucket = int(hashlib.md5(word.encode()).hexdigest(), 16) % EMBEDDING_DIMENSIONS
        vector[bucket] += 1.0
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]


class FakeEmbedder:
    """Stands in for `retrieval.embed_documents`; records calls so tests can assert on them."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, texts: list[str], title: str | None = None) -> list[list[float]]:
        self.calls.append(list(texts))
        return [fake_vector(t) for t in texts]

    @property
    def texts_embedded(self) -> int:
        return sum(len(c) for c in self.calls)


@pytest.fixture
def fake_embedder() -> FakeEmbedder:
    return FakeEmbedder()


@pytest.fixture
def db_conn():
    """A connection whose tables live in a throwaway schema, dropped after the test.

    Skips when PostgreSQL isn't reachable (start it with `docker compose up -d db`).
    """
    from app.db import connect, ensure_schema

    try:
        admin = connect(connect_timeout=3)  # also ensures the `vector` extension is in public
    except ServiceUnavailableError as exc:
        pytest.skip(f"PostgreSQL not available: {exc}")
    schema = f"test_{uuid.uuid4().hex[:12]}"
    admin.execute(f"CREATE SCHEMA {schema}")
    conn = connect(options=f"-c search_path={schema},public")
    try:
        ensure_schema(conn)
        yield conn
    finally:
        conn.close()
        admin.execute(f"DROP SCHEMA {schema} CASCADE")
        admin.close()
