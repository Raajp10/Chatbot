"""Grounded-generation prompt construction and the Gemini generation call. Implemented in T014/T029/T052/T062."""

from app.config import GENERATION_MODEL, ServiceUnavailableError, get_client


def generate_text(prompt: str) -> str:
    """Call Gemini generation on `prompt`, raising ServiceUnavailableError on any SDK-level failure."""
    try:
        response = get_client().models.generate_content(
            model=GENERATION_MODEL,
            contents=prompt,
        )
    except Exception as exc:
        raise ServiceUnavailableError(str(exc)) from exc
    return response.text
