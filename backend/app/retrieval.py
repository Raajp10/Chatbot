"""Chroma store wrapper + similarity search + campus/program/student-level/academic-term metadata filtering + courseName boost. Implemented in T014/T015/T028/T041/T051/T055/T060."""

from typing import Any

import chromadb

from app.config import CHROMA_PATH, EMBEDDING_MODEL, ServiceUnavailableError, get_client

_COLLECTION_NAME = "source_chunks"

# SourceChunk metadata fields (data-model.md); `url` and `title` are required on every
# chunk, the rest are omitted (never guessed) when the manifest entry doesn't supply them.
_METADATA_FIELDS = (
    "url",
    "title",
    "structureContext",
    "campus",
    "academicTerm",
    "courseName",
    "programName",
    "studentLevel",
)

_persistent_client: chromadb.ClientAPI | None = None


def _get_persistent_client() -> chromadb.ClientAPI:
    global _persistent_client
    if _persistent_client is None:
        _persistent_client = chromadb.PersistentClient(path=CHROMA_PATH)
    return _persistent_client


def get_or_create_collection() -> chromadb.Collection:
    return _get_persistent_client().get_or_create_collection(name=_COLLECTION_NAME)


def embed_text(text: str) -> list[float]:
    """Embed `text` via Gemini's embedding API, raising ServiceUnavailableError on any SDK-level failure."""
    try:
        response = get_client().models.embed_content(
            model=EMBEDDING_MODEL,
            contents=text,
        )
    except Exception as exc:
        raise ServiceUnavailableError(str(exc)) from exc
    return response.embeddings[0].values


def _chunk_metadata(chunk: dict[str, Any]) -> dict[str, Any]:
    return {
        field: chunk[field]
        for field in _METADATA_FIELDS
        if chunk.get(field) is not None
    }


def add_chunks(chunks: list[dict[str, Any]]) -> None:
    """Write already-embedded chunks (each a dict with `url`, `title`, `content`, `embedding`,
    and any optional metadata fields). Each chunk gets its own Chroma ID derived from its
    `url` + its index among the chunks sharing that `url` (e.g. `f"{url}#{i}"`)."""
    if not chunks:
        return
    collection = get_or_create_collection()
    per_url_index: dict[str, int] = {}
    ids, embeddings, documents, metadatas = [], [], [], []
    for chunk in chunks:
        url = chunk["url"]
        index = per_url_index.get(url, 0)
        per_url_index[url] = index + 1
        ids.append(f"{url}#{index}")
        embeddings.append(chunk["embedding"])
        documents.append(chunk["content"])
        metadatas.append(_chunk_metadata(chunk))
    collection.add(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)


def delete_chunks_for_url(url: str) -> None:
    """Remove any chunks already stored for `url`, so re-ingestion replaces rather than duplicates."""
    collection = get_or_create_collection()
    collection.delete(where={"url": url})


def query(
    embedding: list[float],
    where: dict[str, Any] | None = None,
    k: int = 5,
) -> list[dict[str, Any]]:
    """Similarity-search the collection, returning up to `k` chunks as dicts (metadata + `content`)."""
    collection = get_or_create_collection()
    query_kwargs: dict[str, Any] = {"query_embeddings": [embedding], "n_results": k}
    if where:
        query_kwargs["where"] = where
    results = collection.query(**query_kwargs)
    documents = results.get("documents") or [[]]
    metadatas = results.get("metadatas") or [[]]
    chunks: list[dict[str, Any]] = []
    for document, metadata in zip(documents[0], metadatas[0]):
        chunk = dict(metadata)
        chunk["content"] = document
        chunks.append(chunk)
    return chunks
