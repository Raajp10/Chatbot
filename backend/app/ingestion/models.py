"""Plain data shapes passed between ingestion stages: manifest entry → parsed blocks → chunks."""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

SourceType = Literal["webpage", "pdf"]

# Optional SourceChunk context fields (data-model.md); copied onto every chunk of a source
# only when the manifest entry supplies them — never guessed.
CONTEXT_FIELDS = ("campus", "academicTerm", "courseName", "programName", "studentLevel")


@dataclass(frozen=True)
class SourceEntry:
    """One approved-source manifest entry (research.md §6)."""

    url: str
    title: str
    id: str
    sourceName: str | None = None
    category: str | None = None
    context: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "SourceEntry":
        url = (raw.get("url") or "").strip()
        title = (raw.get("title") or "").strip()
        if not url or not title:
            raise ValueError(f"Manifest entry needs both 'url' and 'title': {raw!r}")
        if urlparse(url).scheme not in ("http", "https"):
            raise ValueError(f"Manifest entry 'url' must be http(s): {url!r}")
        return cls(
            url=url,
            title=title,
            id=(raw.get("id") or _slug_from_url(url)).strip(),
            sourceName=raw.get("sourceName"),
            category=raw.get("category"),
            context={k: raw[k] for k in CONTEXT_FIELDS if raw.get(k) is not None},
        )


def load_manifest(path: str | Path) -> list[SourceEntry]:
    raw = json.loads(Path(path).read_text())
    if not isinstance(raw, list):
        raise TypeError(f"Manifest {path} must be a JSON list of source entries")
    entries = [SourceEntry.from_dict(item) for item in raw]
    for attr in ("id", "url"):
        values = [getattr(e, attr) for e in entries]
        dupes = {v for v in values if values.count(v) > 1}
        if dupes:
            raise ValueError(f"Duplicate manifest {attr}(s): {sorted(dupes)}")
    return entries


def _slug_from_url(url: str) -> str:
    last = [p for p in urlparse(url).path.split("/") if p][-1:] or ["document"]
    stem = re.sub(r"\.[a-z0-9]+$", "", last[0], flags=re.IGNORECASE)
    return re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-") or "document"


@dataclass(frozen=True)
class Block:
    """One paragraph-level unit of parsed text (a heading, paragraph, list item, table...)."""

    text: str
    heading_path: tuple[str, ...] = ()
    page_number: int | None = None
    is_heading: bool = False


@dataclass
class ParsedDocument:
    source_type: SourceType
    blocks: list[Block]
    page_count: int | None = None

    @property
    def text(self) -> str:
        return "\n\n".join(b.text for b in self.blocks)


@dataclass(frozen=True)
class Chunk:
    chunk_index: int
    content: str
    structure_context: str | None = None
    page_number: int | None = None
    page_end: int | None = None
