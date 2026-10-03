"""Light, wording-preserving text cleanup shared by the parsers. Never summarizes or rewrites."""

import re
import unicodedata
from collections import Counter

_ZERO_WIDTH = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff\u00ad"), None)
_PAGE_MARKER = re.compile(r"^\s*(page\s+)?\d+(\s*(of|/)\s*\d+)?\s*$", re.IGNORECASE)


def normalize_inline(text: str) -> str:
    """Collapse all whitespace (including newlines) to single spaces."""
    text = unicodedata.normalize("NFKC", text).translate(_ZERO_WIDTH)
    text = re.sub(r"\s+", " ", text).strip()
    # Inline tags split by whitespace in the HTML leave stray spaces before punctuation.
    text = re.sub(r" +([,.;:!?)\]])", r"\1", text)
    text = re.sub(r"([(\[]) +", r"\1", text)
    # Long fill-in-the-blank underscores (PDF forms) carry no meaning beyond "a blank".
    return re.sub(r"_{4,}", "___", text)


def normalize_text(text: str) -> str:
    """Normalize spaces within lines and blank-line runs between them, keeping line structure."""
    lines = [normalize_inline(line) for line in text.replace("\r\n", "\n").split("\n")]
    text = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def is_page_marker(line: str) -> bool:
    """`Page 3 of 6`, `3 / 6`, bare `3`, etc."""
    return bool(_PAGE_MARKER.match(line))


def repeated_page_lines(pages: list[list[str]], min_pages: int = 3) -> set[str]:
    """Lines (digits masked) that repeat on most pages — running headers/footers."""
    if len(pages) < min_pages:
        return set()
    counts = Counter(
        key for lines in pages for key in {_mask_digits(line) for line in lines if line.strip()}
    )
    threshold = max(min_pages, (len(pages) + 1) // 2 + 1)
    return {key for key, n in counts.items() if n >= threshold}


def strip_repeated_lines(lines: list[str], repeated: set[str]) -> list[str]:
    return [line for line in lines if _mask_digits(line) not in repeated]


def _mask_digits(line: str) -> str:
    return re.sub(r"\d+", "#", line.strip().lower())
