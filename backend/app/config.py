"""Env/config loader (GEMINI_API_KEY, DATABASE_URL); shared Gemini client setup. Implemented in T013."""

import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai

# Pick up backend/.env when running on the host. Never overrides variables already set, so
# docker-compose.yml's `env_file`/`environment` still win inside the container.
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
# Host-side default matches docker-compose.yml's `db` service published on localhost:5433;
# inside the `backend` container docker-compose.yml overrides this to point at `db:5432`.
DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://pnw:pnw@localhost:5433/pnw_chatbot"
)

GENERATION_MODEL = "gemini-2.5-flash"
EMBEDDING_MODEL = "gemini-embedding-001"
# gemini-embedding-001 defaults to 3072 dimensions; pgvector's HNSW index supports at most
# 2000, so we request Gemini's recommended reduced size. `chunks.embedding` is VECTOR(768).
EMBEDDING_DIMENSIONS = 768


class ServiceUnavailableError(Exception):
    """Raised when the Gemini API or the PostgreSQL/pgvector store cannot be reached."""


class ConfigurationError(ServiceUnavailableError):
    """Raised when required configuration (e.g. GEMINI_API_KEY) is missing."""


_client: genai.Client | None = None


def get_client() -> genai.Client:
    """Return the shared Gemini SDK client, created lazily on first use."""
    global _client
    if _client is None:
        if not GEMINI_API_KEY or GEMINI_API_KEY == "your-key-here":
            raise ConfigurationError(
                "GEMINI_API_KEY is not set. Copy backend/.env.example to backend/.env and set "
                "GEMINI_API_KEY to your Google Gemini API key "
                "(https://aistudio.google.com/apikey)."
            )
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client
