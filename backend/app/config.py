"""Env/config loader (GEMINI_API_KEY, CHROMA_PATH); shared Gemini client setup. Implemented in T013."""

import os

from google import genai

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
CHROMA_PATH = os.environ.get("CHROMA_PATH", "/app/data/chroma")

GENERATION_MODEL = "gemini-2.5-flash"
EMBEDDING_MODEL = "gemini-embedding-001"


class ServiceUnavailableError(Exception):
    """Raised when the Gemini API or the local Chroma store cannot be reached."""


_client: genai.Client | None = None


def get_client() -> genai.Client:
    """Return the shared Gemini SDK client, created lazily on first use."""
    global _client
    if _client is None:
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client
