from typing import ClassVar

import pytest

from app.ingestion.parsers import ParseError
from app.ingestion.parsers.html_parser import parse_html
from app.ingestion.parsers.pdf_parser import parse_pdf
from tests.conftest import make_pdf

URL = "https://www.pnw.edu/dean-of-students/policies/example-policy/"

# Modeled on the real pnw.edu policy page layout (header/nav/sidebar chrome around
# `.main__content`, tab panels labelled by toggle buttons, bold-titled nested lists, a table).
POLICY_HTML = f"""
<html><head><title>Example Policy - PNW</title><link rel="canonical" href="{URL}"></head>
<body>
  <header class="site-header"><nav><a href="/">Home</a><a href="/apply">Apply Now</a></nav></header>
  <div class="cookie-banner">We use cookies. <button>Accept</button></div>
  <main class="page-content"><div class="main">
    <div class="breadcrumb"><a href="/">PNW</a> / Policies</div>
    <div class="main__sidebar"><nav class="subnav"><ul><li>Other Policy</li></ul></nav></div>
    <div class="main__content">
      <h1>Example Policy</h1>
      <p>Students   must notify   their <a href="#">instructor</a> , in writing.</p>
      <h2>Excused Absence Categories</h2>
      <div class="tabs">
        <div class="tabs__nav"><button class="tabs__button">Grief</button></div>
        <div class="tabs__content">
          <button class="accordion__toggle tabs__toggle">Grief</button>
          <div class="tabs__content__item"><p>Up to five days for immediate family.</p></div>
        </div>
      </div>
      <ol><li><ol>
        <li><strong>Preamble</strong><ol><li>Grades are a measure of achievement.</li></ol></li>
      </ol></li></ol>
      <table><thead><tr><th>Action</th><th>Due By</th></tr></thead>
        <tbody><tr><td>Notice of Intention</td><td>21st Day</td></tr></tbody></table>
    </div>
  </div></main>
  <footer>© Purdue University Northwest. All rights reserved.</footer>
</body></html>
"""


class TestHtmlParser:
    def test_extracts_policy_text_without_page_chrome(self):
        text = parse_html(POLICY_HTML, URL).text
        assert "Students must notify their instructor, in writing." in text
        assert "Up to five days for immediate family." in text
        for chrome in ("Apply Now", "cookies", "All rights reserved", "Other Policy", "Accept"):
            assert chrome not in text

    def test_keeps_headings_and_tab_labels_in_heading_path(self):
        blocks = parse_html(POLICY_HTML, URL).blocks
        grief = next(b for b in blocks if b.text.startswith("Up to five days"))
        assert grief.heading_path == ("Example Policy", "Excused Absence Categories", "Grief")
        assert any(b.is_heading and b.text == "Example Policy" for b in blocks)

    def test_bold_list_title_becomes_heading_and_numbering_is_kept(self):
        blocks = parse_html(POLICY_HTML, URL).blocks
        item = next(b for b in blocks if "Grades are a measure" in b.text)
        assert item.text == "1. Grades are a measure of achievement."
        assert item.heading_path[-1] == "Preamble"

    def test_table_rows_keep_column_headers(self):
        assert "Action: Notice of Intention; Due By: 21st Day" in parse_html(POLICY_HTML, URL).text

    def test_rejects_a_different_page_served_with_200(self):
        fallback = POLICY_HTML.replace(f'href="{URL}"', 'href="https://www.purdue.edu/home/"')
        with pytest.raises(ParseError, match="different page"):
            parse_html(fallback, URL)

    def test_rejects_page_without_meaningful_text(self):
        with pytest.raises(ParseError):
            parse_html("<html><body><nav>Menu</nav><main><p>Hi</p></main></body></html>", URL)


class TestPdfParser:
    PAGES: ClassVar[list[list[str]]] = [
        [
            "Page 1 of 3",
            "Classroom Behavior Policy",
            "Preamble",
            "Purdue University Northwest supports the principles of freedom of expression for both",
            "faculty and students. Disruptive behavior will not be tolerated.",
            "1. Communicate in a professional and courteous manner.",
            "2. Respect faculty, staff, and fellow students.",
        ],
        ["Page 2 of 3"],  # a page with no text besides the running header
        [
            "Page 3 of 3",
            "Counseling Center",
            "The Counseling Center provides counseling to students experiencing concerns.",
            "o refer the student to the Dean of Students",
        ],
    ]

    def test_extracts_text_page_by_page(self):
        doc = parse_pdf(make_pdf(self.PAGES), "https://example.edu/policy.pdf")
        assert doc.source_type == "pdf"
        assert doc.page_count == 3
        assert "Disruptive behavior will not be tolerated." in doc.text
        counseling = next(b for b in doc.blocks if b.text.startswith("The Counseling Center"))
        assert counseling.page_number == 3
        assert counseling.heading_path == ("Counseling Center",)

    def test_rejoins_wrapped_lines_and_splits_list_items(self):
        doc = parse_pdf(make_pdf(self.PAGES), "https://example.edu/policy.pdf")
        texts = [b.text for b in doc.blocks]
        assert (
            "Purdue University Northwest supports the principles of freedom of expression for "
            "both faculty and students. Disruptive behavior will not be tolerated."
        ) in texts
        assert "1. Communicate in a professional and courteous manner." in texts
        assert "  - refer the student to the Dean of Students" in texts

    def test_drops_page_markers_and_skips_empty_pages(self):
        doc = parse_pdf(make_pdf(self.PAGES), "https://example.edu/policy.pdf")
        assert "Page" not in doc.text.split()[0:3]
        assert not any("of 3" in b.text for b in doc.blocks)
        assert {b.page_number for b in doc.blocks} == {1, 3}

    def test_pdf_without_text_is_an_error(self):
        with pytest.raises(ParseError, match="no extractable text"):
            parse_pdf(make_pdf([[], []]), "https://example.edu/scan.pdf")

    def test_corrupt_pdf_is_an_error(self):
        with pytest.raises(ParseError):
            parse_pdf(b"%PDF-1.4 this is not really a pdf", "https://example.edu/bad.pdf")
