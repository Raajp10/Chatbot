"""HTML parser (BeautifulSoup) — structure-preserving text extraction. Implemented in T023.

Output is a flat list of `Block`s in document order, each carrying the heading path it sits
under, so the chunker can split on section boundaries and record `structureContext`:
  - headings (h1–h6) build the heading path;
  - tab/accordion labels (`button.*toggle*`, `<summary>`) become sub-headings, so content that
    is only shown after clicking "Grief" still says it's about grief;
  - list items keep their numbering/bullets and nesting; an `<li>` whose own text is just a
    bold title followed by a nested list is treated as a section heading;
  - tables are flattened row by row as "Header: value; Header: value" so each value keeps its
    column header (FR-014).
"""

import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

from app.ingestion.cleaning import normalize_inline
from app.ingestion.models import Block, ParsedDocument
from app.ingestion.parsers import ParseError

# First match wins: narrowest known content container → generic fallbacks.
_CONTENT_SELECTORS = (".main__content", "main article", "article", "main", "[role=main]", "body")
_CHROME_SELECTORS = (
    "script", "style", "noscript", "template", "svg", "iframe", "form", "nav", "aside",
    "footer", ".breadcrumb", ".subnav", ".tabs__nav", ".screen-reader-text", ".sr-only",
    "[class*=cookie]", "[id*=cookie]", "[class*=consent]", "[aria-hidden=true]",
)
_BLOCK_TAGS = {
    "address", "article", "blockquote", "dd", "details", "div", "dl", "dt", "figcaption",
    "figure", "h1", "h2", "h3", "h4", "h5", "h6", "header", "hr", "li", "main", "ol", "p",
    "pre", "section", "table", "ul",
}
_BLOCK_TAG_LIST = sorted(_BLOCK_TAGS)
_LABEL_ATTR = "data-ingest-label"
_LABEL_LEVEL = 7  # deeper than any h-tag: labels nest under the current heading, replace siblings
_MIN_TEXT_CHARS = 50


def parse_html(html: str | bytes, url: str) -> ParsedDocument:
    soup = BeautifulSoup(html, "html.parser")
    _check_canonical(soup, url)

    root = next((el for sel in _CONTENT_SELECTORS if (el := soup.select_one(sel))), soup)
    _strip_chrome(root)

    walker = _Walker()
    walker.walk(root)
    blocks = _drop_consecutive_duplicates(walker.blocks)
    if sum(len(b.text) for b in blocks if not b.is_heading) < _MIN_TEXT_CHARS:
        raise ParseError(f"No meaningful text found in {url}")
    return ParsedDocument(source_type="webpage", blocks=blocks)


def _check_canonical(soup: BeautifulSoup, url: str) -> None:
    """Reject a 200 response that's really some other page (e.g. a bot-block fallback)."""
    link = soup.find("link", rel="canonical")
    href = link.get("href") if isinstance(link, Tag) else None
    if href and _url_key(href) != _url_key(url):
        raise ParseError(
            f"Server returned a different page than requested for {url} (canonical: {href})"
        )


def _url_key(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    return parsed.netloc.lower().removeprefix("www."), parsed.path.rstrip("/").lower()


def _strip_chrome(root: Tag) -> None:
    for comment in root.find_all(string=lambda s: isinstance(s, Comment)):
        comment.extract()
    # Tab/accordion toggles label the panel that follows them — keep them as labels.
    for el in root.select("button[class*=toggle], button[aria-controls], summary"):
        el.name = "p"
        el.attrs = {_LABEL_ATTR: "1"}
    for el in root.select("button"):
        el.decompose()
    for el in root.select(", ".join(_CHROME_SELECTORS)):
        if not el.decomposed:
            el.decompose()
    for header in root.find_all("header"):
        # A page/article <header> holding the h1 is content; a site header is chrome.
        if header.find("h1"):
            header.unwrap()
        else:
            header.decompose()
    for br in root.find_all("br"):
        br.replace_with(" ")


def _drop_consecutive_duplicates(blocks: list[Block]) -> list[Block]:
    out: list[Block] = []
    for block in blocks:
        if out and out[-1].text == block.text and out[-1].is_heading == block.is_heading:
            continue
        out.append(block)
    return out


def _is_block(el: Tag) -> bool:
    return el.name in _BLOCK_TAGS or el.has_attr(_LABEL_ATTR) or el.find(_BLOCK_TAG_LIST) is not None


def _inline_text(node: Tag | NavigableString) -> str:
    return normalize_inline(node.get_text(" ") if isinstance(node, Tag) else str(node))


class _Walker:
    def __init__(self) -> None:
        self.blocks: list[Block] = []
        self._headings: list[tuple[int, str]] = []
        # List depth whose items sit directly under the current list-item heading, so their
        # indentation is relative to that heading rather than to the outermost list.
        self._indent_base = 0

    @property
    def _path(self) -> tuple[str, ...]:
        return tuple(text for _, text in self._headings)

    def _emit(self, text: str) -> None:
        if text:
            self.blocks.append(Block(text=text, heading_path=self._path))

    def _heading(self, level: int, text: str) -> None:
        if not text:
            return
        while self._headings and self._headings[-1][0] >= level:
            self._headings.pop()
        self._headings.append((level, text))
        self._indent_base = 0
        self.blocks.append(Block(text=text, heading_path=self._path, is_heading=True))

    def walk(self, node: Tag) -> None:
        buffer: list[str] = []
        for child in node.children:
            if isinstance(child, Tag) and _is_block(child):
                self._emit(normalize_inline(" ".join(buffer)))
                buffer = []
                self._block(child)
            elif isinstance(child, (Tag, NavigableString)):
                buffer.append(child.get_text(" ") if isinstance(child, Tag) else str(child))
        self._emit(normalize_inline(" ".join(buffer)))

    def _block(self, el: Tag) -> None:
        if re.fullmatch(r"h[1-6]", el.name):
            self._heading(int(el.name[1]), _inline_text(el))
        elif el.has_attr(_LABEL_ATTR):
            self._heading(_LABEL_LEVEL, _inline_text(el))
        elif el.name in ("ul", "ol"):
            self._list(el, depth=0)
        elif el.name == "table":
            self._emit(_table_text(el))
        elif el.name == "hr":
            return
        else:
            self.walk(el)

    def _list(self, lst: Tag, depth: int) -> None:
        number = int(lst.get("start", 1)) if str(lst.get("start", "1")).isdigit() else 1
        for li in lst.find_all("li", recursive=False):
            nested = [c for c in li.children if isinstance(c, Tag) and c.name in ("ul", "ol")]
            own_parts = [c for c in li.children if c not in nested]
            own = normalize_inline(
                " ".join(c.get_text(" ") if isinstance(c, Tag) else str(c) for c in own_parts)
            )
            if own and nested and _is_bold_title(own_parts, own):
                self._heading(3 + depth, own)
                self._indent_base = depth + 1
            elif own:
                marker = f"{number}." if lst.name == "ol" else "-"
                self._emit(f"{'  ' * max(0, depth - self._indent_base)}{marker} {own}")
            for sub in nested:
                self._list(sub, depth + 1)
            number += 1


def _is_bold_title(parts: list, own: str) -> bool:
    tags = [p for p in parts if isinstance(p, Tag)]
    return (
        len(own) <= 120
        and len(tags) == 1
        and tags[0].name in ("strong", "b")
        and _inline_text(tags[0]) == own
    )


def _table_text(table: Tag) -> str:
    rows = [
        [_inline_text(cell) for cell in tr.find_all(["th", "td"], recursive=False)]
        for tr in table.find_all("tr")
    ]
    rows = [r for r in rows if any(r)]
    if not rows:
        return ""
    first_tr = table.find("tr")
    has_header = first_tr is not None and all(c.name == "th" for c in first_tr.find_all(["th", "td"]))
    lines = []
    caption = table.find("caption")
    if caption:
        lines.append(_inline_text(caption))
    if has_header and len(rows) > 1:
        header, body = rows[0], rows[1:]
        for row in body:
            pairs = [f"{h}: {v}" if h else v for h, v in zip(header, row) if v]
            lines.append("; ".join(pairs))
    else:
        lines.extend(" | ".join(c for c in row if c) for row in rows)
    return "\n".join(lines)
