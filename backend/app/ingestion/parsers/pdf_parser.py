"""PDF parser (pypdf) — text extraction with page/section structure preserved. Implemented in T024.

pypdf returns each page as hard-wrapped lines. This rebuilds paragraphs from them:
  - running headers/footers (e.g. "Page 3 of 6") are dropped;
  - a short Title Case line with no trailing punctuation that starts a new block is a heading;
  - list items (1., a., •, o, -) start new blocks;
  - a line ending a sentence that's noticeably shorter than the page's text width ends a paragraph;
  - everything else is a wrapped continuation of the current paragraph.
Every block records the page it came from. No OCR — a PDF with no extractable text is an error.
"""

import logging
import re
from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.ingestion.cleaning import (
    is_page_marker,
    normalize_inline,
    repeated_page_lines,
    strip_repeated_lines,
)
from app.ingestion.models import Block, ParsedDocument
from app.ingestion.parsers import ParseError

logger = logging.getLogger(__name__)

_LIST_ITEM = re.compile(r"^(\d{1,2}[.)]|[a-z][.)]|[•●▪◦‣*\-–]|o)\s+")
_SUB_BULLET = re.compile(r"^o\s+")
_BULLET = re.compile(r"^[•●▪◦‣*–]\s+")
_SMALL_WORDS = {"a", "an", "and", "as", "at", "by", "for", "from", "in", "of", "on", "or",
                "the", "to", "with", "vs"}
_MAX_HEADING_CHARS = 90
_PARAGRAPH_END_RATIO = 0.8  # a sentence-ending line shorter than this × page width ends a paragraph


def parse_pdf(data: bytes, url: str) -> ParsedDocument:
    logging.getLogger("pypdf").setLevel(logging.ERROR)  # malformed-xref noise, not actionable
    try:
        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted:
            reader.decrypt("")
        raw_pages = [_page_text(page, i, url) for i, page in enumerate(reader.pages, start=1)]
    except PdfReadError as exc:
        raise ParseError(f"Could not read PDF {url}: {exc}") from exc

    page_lines = [
        [line for line in map(normalize_inline, text.splitlines()) if line and not is_page_marker(line)]
        for text in raw_pages
    ]
    repeated = repeated_page_lines(page_lines)

    blocks: list[Block] = []
    heading: str | None = None
    for page_number, lines in enumerate(page_lines, start=1):
        lines = strip_repeated_lines(lines, repeated)
        if not lines:
            logger.info("PDF %s page %d has no extractable text; skipping", url, page_number)
            continue
        page_blocks, heading = _page_blocks(lines, page_number, heading)
        blocks.extend(page_blocks)

    if not any(not b.is_heading for b in blocks):
        raise ParseError(
            f"PDF {url} has no extractable text (it may be scanned images; OCR is not supported)"
        )
    return ParsedDocument(source_type="pdf", blocks=blocks, page_count=len(raw_pages))


def _page_text(page, page_number: int, url: str) -> str:
    try:
        return page.extract_text() or ""
    except Exception as exc:  # noqa: BLE001 — one bad page shouldn't sink the whole document
        logger.warning("Could not extract text from %s page %d: %s", url, page_number, exc)
        return ""


def _page_blocks(
    lines: list[str], page_number: int, heading: str | None
) -> tuple[list[Block], str | None]:
    width = max(len(line) for line in lines)
    blocks: list[Block] = []
    paragraph: list[str] = []
    prev: str | None = None
    prev_was_heading = False

    def flush() -> None:
        if paragraph:
            blocks.append(
                Block(
                    text=" ".join(paragraph),
                    heading_path=(heading,) if heading else (),
                    page_number=page_number,
                )
            )
            paragraph.clear()

    for line in lines:
        block_ended = (
            prev is None
            or prev_was_heading
            or (prev[-1] in ".!?:;" or prev.endswith(", and"))
            or len(prev) < _PARAGRAPH_END_RATIO * width
        )
        wrapped_heading = (
            prev_was_heading and prev is not None and len(prev) >= 0.6 * width
            and len(line) <= 40 and line[0].isupper() and not _LIST_ITEM.match(line)
        )
        if wrapped_heading:
            # A long heading wrapped onto a second line.
            heading = f"{heading} {line.rstrip(':')}"
            blocks[-1] = Block(text=heading, heading_path=(heading,),
                               page_number=page_number, is_heading=True)
        elif _LIST_ITEM.match(line):
            flush()
            paragraph.append(_normalize_bullet(line))
            prev_was_heading = False
        elif block_ended and _looks_like_heading(line):
            flush()
            heading = line
            blocks.append(Block(text=line, heading_path=(line,),
                                page_number=page_number, is_heading=True))
            prev_was_heading = True
        elif paragraph and prev and prev[-1] in ".!?:" and len(prev) < _PARAGRAPH_END_RATIO * width:
            flush()
            paragraph.append(line)
            prev_was_heading = False
        else:
            paragraph.append(line)
            prev_was_heading = False
        prev = line
    flush()
    return blocks, heading


def _looks_like_heading(line: str) -> bool:
    if (
        len(line) > _MAX_HEADING_CHARS
        or line[-1] in ".,;:"
        or not line[0].isupper()
        or "_" in line  # form fields ("Signature:___")
    ):
        return False
    words = re.findall(r"[A-Za-z][A-Za-z’'-]*", line)
    significant = [w for i, w in enumerate(words) if i == 0 or w.lower() not in _SMALL_WORDS]
    if not significant:
        return False
    capitalized = sum(w[0].isupper() for w in significant)
    return capitalized >= 0.8 * len(significant)


def _normalize_bullet(line: str) -> str:
    if _SUB_BULLET.match(line):
        return _SUB_BULLET.sub("  - ", line)
    return _BULLET.sub("- ", line)
