import pytest

from helpers.text_splitter import split_text

PARAGRAPHS = (
    "Retrieval-augmented generation combines search with a language model.\n\n"
    "First, documents are split into chunks and indexed.\n"
    "Then, the most relevant chunks are retrieved for each question.\n\n"
    "Finally, the model answers using the retrieved context."
)


def test_short_text_is_one_chunk():
    assert split_text("Hello world.", chunk_size=100) == ["Hello world."]


@pytest.mark.parametrize("text", ["", "   ", "\n\n\n"])
def test_blank_text_gives_no_chunks(text):
    assert split_text(text, chunk_size=100) == []


@pytest.mark.parametrize("chunk_size", [20, 50, 80, 200])
def test_chunks_never_exceed_chunk_size(chunk_size):
    chunks = split_text(PARAGRAPHS, chunk_size=chunk_size, overlap_size=10)

    assert chunks
    assert all(len(chunk) <= chunk_size for chunk in chunks)


@pytest.mark.parametrize("chunk_size", [20, 50, 80])
def test_no_words_are_lost(chunk_size):
    chunks = split_text(PARAGRAPHS, chunk_size=chunk_size)

    assert " ".join(chunks).split() == PARAGRAPHS.split()


def test_prefers_paragraph_boundaries():
    text = "a" * 30 + "\n\n" + "b" * 30

    assert split_text(text, chunk_size=40) == ["a" * 30, "b" * 30]


def test_consecutive_chunks_overlap():
    text = " ".join(f"w{i}" for i in range(40))

    chunks = split_text(text, chunk_size=30, overlap_size=10)

    for previous, following in zip(chunks, chunks[1:], strict=False):
        assert previous.split()[-1] in following.split()


def test_word_longer_than_chunk_size_is_cut():
    chunks = split_text("x" * 25, chunk_size=10)

    assert chunks == ["x" * 10, "x" * 10, "x" * 5]


@pytest.mark.parametrize(
    ("chunk_size", "overlap_size"),
    [(0, 0), (-5, 0), (10, 10), (10, 20), (10, -1)],
)
def test_invalid_sizes_raise(chunk_size, overlap_size):
    with pytest.raises(ValueError):
        split_text("text", chunk_size=chunk_size, overlap_size=overlap_size)
