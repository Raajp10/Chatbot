"""Structure-aware chunker. Implemented in T026.

Packs parsed `Block`s into chunks of at most `max_chars` characters, preferring to break at:
  1. section headings (a new heading starts a new chunk once the current one is big enough),
  2. block boundaries (paragraphs, list items, table rows),
  3. sentence boundaries (only inside a block too large to fit on its own),
  4. word boundaries (only inside a single sentence too large to fit on its own).
When a chunk is closed because it's full (not at a heading), the next chunk starts with up to
`overlap_chars` of the previous chunk's trailing sentences so context isn't lost at the seam.

Each chunk's content begins with the heading path it sits under ("Policy > Section"), which is
also stored as `structure_context`. Output is deterministic: the same blocks always produce the
same chunks, indexes and text. Empty and duplicate chunks are dropped.
"""

import hashlib
import re
from dataclasses import replace

from app.ingestion.models import Block, Chunk

# Gemini tokenizes English at roughly 4 characters per token.
MAX_CHARS = 2400  # ≈ 600 tokens
OVERLAP_CHARS = 360  # 15% of MAX_CHARS
MIN_CHARS = 800  # don't close a chunk at a heading until it has at least this much text

_SENTENCE_BREAK = re.compile(r"(?<=[.!?;])\s+(?=[\"“(\[]?[A-Z0-9])")
_LIST_ITEM = re.compile(r"^\s*(\d{1,2}[.)]|[a-z][.)]|-)\s")


def chunk_blocks(
    blocks: list[Block],
    max_chars: int = MAX_CHARS,
    overlap_chars: int = OVERLAP_CHARS,
    min_chars: int = MIN_CHARS,
) -> list[Chunk]:
    if not 0 <= overlap_chars < max_chars or min_chars > max_chars:
        raise ValueError("Require 0 <= overlap_chars < max_chars and min_chars <= max_chars")

    pieces = [
        piece
        for block in blocks
        if block.text.strip()
        for piece in _split_oversized(block, max_chars - len(_breadcrumb(block)) - 2)
    ]

    groups: list[list[Block]] = []
    current: list[Block] = []
    overlap_count = 0  # leading blocks of `current` that are overlap copied from the last chunk

    for piece in pieces:
        own = current[overlap_count:]
        if piece.is_heading and own and len(_render(own)) >= min_chars:
            groups.append(current)
            current, overlap_count = [], 0
        elif piece.is_heading and not own:
            current, overlap_count = [], 0  # a new section starts: drop the pending overlap
        elif current and len(_render(current + [piece])) > max_chars:
            # Don't strand headings at the end of a chunk; carry them into the next one.
            carried: list[Block] = []
            while current and current[-1].is_heading:
                carried.insert(0, current.pop())
            if current[overlap_count:]:
                groups.append(current)
                overlap = [] if carried else _overlap(current, overlap_chars)
            else:
                overlap = []
            if overlap and len(_render(overlap + [piece])) > max_chars:
                overlap = []
            current, overlap_count = overlap + carried, len(overlap)
        current.append(piece)

    if current[overlap_count:] and any(not b.is_heading for b in current[overlap_count:]):
        groups.append(current)
    if (
        len(groups) > 1
        and len(_render(groups[-1])) < min_chars
        and len(_render(groups[-2] + groups[-1])) <= max_chars
    ):
        groups[-2:] = [groups[-2] + groups[-1]]

    chunks: list[Chunk] = []
    seen: set[str] = set()
    for group in groups:
        content = _render(group)
        key = hashlib.sha256(re.sub(r"\s+", " ", content).lower().encode()).hexdigest()
        if not content.strip() or key in seen:
            continue
        seen.add(key)
        pages = [b.page_number for b in group if b.page_number is not None]
        path = group[0].heading_path
        chunks.append(
            Chunk(
                chunk_index=len(chunks),
                content=content,
                structure_context=" > ".join(path) if path else None,
                page_number=min(pages) if pages else None,
                page_end=max(pages) if pages else None,
            )
        )
    return chunks


def _breadcrumb(block: Block) -> str:
    return " > ".join(block.heading_path)


def _render(group: list[Block]) -> str:
    """Chunk text: heading-path breadcrumb, then the blocks (a leading heading is the breadcrumb)."""
    if not group:
        return ""
    parts: list[str] = []
    breadcrumb = _breadcrumb(group[0])
    body = group[1:] if group[0].is_heading else group
    if breadcrumb:
        parts.append(breadcrumb)
    prev: Block | None = None
    for block in body:
        if parts:
            tight = prev is not None and _LIST_ITEM.match(prev.text) and _LIST_ITEM.match(block.text)
            parts.append("\n" if tight else "\n\n")
        parts.append(block.text)
        prev = block
    return "".join(parts).strip()


def _split_oversized(block: Block, limit: int) -> list[Block]:
    limit = max(limit, 200)
    if len(block.text) <= limit:
        return [block]
    units: list[str] = []
    for line in block.text.split("\n"):
        for sentence in _SENTENCE_BREAK.split(line):
            units.extend(_hard_split(sentence.strip(), limit))
    pieces: list[str] = []
    for unit in filter(None, units):
        if pieces and len(pieces[-1]) + 1 + len(unit) <= limit:
            pieces[-1] = f"{pieces[-1]} {unit}"
        else:
            pieces.append(unit)
    return [replace(block, text=text) for text in pieces]


def _hard_split(text: str, limit: int) -> list[str]:
    out: list[str] = []
    while len(text) > limit:
        cut = text.rfind(" ", 0, limit)
        cut = cut if cut > 0 else limit
        out.append(text[:cut].strip())
        text = text[cut:].strip()
    return out + [text] if text else out


def _overlap(group: list[Block], overlap_chars: int) -> list[Block]:
    """The trailing sentences of the group's last text block, up to `overlap_chars`."""
    if overlap_chars <= 0:
        return []
    last = next((b for b in reversed(group) if not b.is_heading), None)
    if last is None:
        return []
    sentences = _SENTENCE_BREAK.split(last.text)
    tail: list[str] = []
    for sentence in reversed(sentences):
        if len(" ".join([sentence, *tail])) > overlap_chars:
            break
        tail.insert(0, sentence)
    if not tail:
        # A single long final sentence: take its last `overlap_chars` at a word boundary.
        text = last.text[-overlap_chars:]
        tail = [text[text.find(" ") + 1:] if " " in text else text]
    return [replace(last, text=" ".join(tail).strip(), is_heading=False)]
