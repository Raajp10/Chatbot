from itertools import pairwise

import pytest

from app.ingestion.chunker import chunk_blocks
from app.ingestion.models import Block


def _section(title: str, paragraphs: int, sentence: str, page: int | None = None) -> list[Block]:
    path = ("Policy", title)
    return [Block(title, path, page, is_heading=True)] + [
        Block(" ".join(f"{sentence} number {p}-{s}." for s in range(6)), path, page)
        for p in range(paragraphs)
    ]


BLOCKS = (
    [Block("Policy", ("Policy",), is_heading=True)]
    + _section("Attendance", 6, "Students must attend every scheduled class session", 1)
    + _section("Grades", 6, "Instructors assign grades using the published rubric", 2)
    + _section("Appeals", 2, "A student may appeal a final grade in writing", 3)
)


def test_empty_input_produces_no_chunks():
    assert chunk_blocks([]) == []
    assert chunk_blocks([Block("   "), Block("")]) == []


def test_headings_alone_produce_no_chunks():
    assert chunk_blocks([Block("Title", ("Title",), is_heading=True)]) == []


@pytest.mark.parametrize("max_chars,overlap", [(400, 60), (800, 120), (2400, 360)])
def test_chunk_sizes_stay_within_bounds(max_chars, overlap):
    chunks = chunk_blocks(BLOCKS, max_chars=max_chars, overlap_chars=overlap, min_chars=100)
    assert len(chunks) > 1
    assert all(0 < len(c.content) <= max_chars for c in chunks)
    assert all(c.content.strip() for c in chunks)


def test_oversized_single_block_is_split_at_sentences():
    long_block = Block(" ".join(f"Sentence {i} explains a rule." for i in range(200)), ("P",))
    chunks = chunk_blocks([long_block], max_chars=500, overlap_chars=50, min_chars=100)
    assert len(chunks) > 1
    assert all(len(c.content) <= 500 for c in chunks)
    body = [c.content.removeprefix("P\n\n") for c in chunks]
    assert all(b.rstrip().endswith(".") for b in body)  # breaks fall on sentence boundaries


def test_chunking_is_deterministic_with_sequential_indexes():
    first = chunk_blocks(BLOCKS, max_chars=800, overlap_chars=120, min_chars=200)
    second = chunk_blocks(BLOCKS, max_chars=800, overlap_chars=120, min_chars=200)
    assert first == second
    assert [c.chunk_index for c in first] == list(range(len(first)))


def test_metadata_survives_chunking():
    chunks = chunk_blocks(BLOCKS, max_chars=800, overlap_chars=120, min_chars=200)
    grades = [c for c in chunks if "published rubric" in c.content]
    assert grades
    assert all(c.structure_context == "Policy > Grades" for c in grades if c.content.startswith("Policy > Grades"))
    assert {c.page_number for c in grades} <= {1, 2}
    appeals = next(c for c in chunks if "appeal a final grade" in c.content)
    assert appeals.page_end == 3
    # Every chunk starts with its heading path so it's traceable/meaningful on its own.
    assert all(c.content.startswith(c.structure_context) for c in chunks)


def test_new_section_starts_new_chunk_once_current_is_big_enough():
    chunks = chunk_blocks(BLOCKS, max_chars=2400, overlap_chars=360, min_chars=200)
    assert any(c.content.startswith("Policy > Grades\n\nInstructors") for c in chunks)
    assert not any("rubric" in c.content and "attend every" in c.content for c in chunks)


def test_size_splits_overlap_with_previous_chunk():
    chunks = chunk_blocks(BLOCKS, max_chars=600, overlap_chars=150, min_chars=100)
    seams = [
        (a, b) for a, b in pairwise(chunks) if a.structure_context == b.structure_context
    ]
    assert seams
    for a, b in seams:
        last_sentence = a.content.rsplit(". ", 1)[-1].rstrip(".")
        assert last_sentence in b.content


def test_duplicate_chunks_are_dropped():
    section = _section("Repeated", 1, "This identical section appears twice on the page")
    chunks = chunk_blocks(section + section, max_chars=400, overlap_chars=0, min_chars=100)
    contents = [c.content for c in chunks]
    assert len(contents) == len(set(contents)) == 1
    assert [c.chunk_index for c in chunks] == [0]


def test_tiny_trailing_chunk_is_merged_into_previous():
    blocks = _section("Main", 1, "A reasonably sized paragraph of policy text") + [
        Block("Contact", ("Policy", "Contact"), is_heading=True),
        Block("Email the dean.", ("Policy", "Contact")),
    ]
    chunks = chunk_blocks(blocks, max_chars=2400, overlap_chars=0, min_chars=200)
    assert len(chunks) == 1
    assert chunks[0].content.endswith("Contact\n\nEmail the dean.")


def test_invalid_parameters_rejected():
    with pytest.raises(ValueError):
        chunk_blocks(BLOCKS, max_chars=100, overlap_chars=100)
