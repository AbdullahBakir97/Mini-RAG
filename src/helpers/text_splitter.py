"""Recursive character text splitter.

Splits text into chunks of at most ``chunk_size`` characters, preferring to
break on paragraph boundaries, then lines, then words, and only cutting inside
a word when a single word is longer than ``chunk_size``. Consecutive chunks
share up to ``overlap_size`` characters of context.
"""

from collections import deque

DEFAULT_SEPARATORS =("\n\n", "\n", " ", "")


def split_text(text: str, chunk_size: int, overlap_size: int = 0,
               separators: tuple[str, ...] = DEFAULT_SEPARATORS) -> list[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if not 0 <= overlap_size < chunk_size:
        raise ValueError("overlap_size must be >= 0 and smaller than chunk_size")

    chunks = _split(text, separators, chunk_size, overlap_size)
    return [chunk.strip() for chunk in chunks if chunk.strip()]


def _split(text: str, separators: tuple[str, ...], chunk_size: int,
           overlap_size: int) -> list[str]:
    # Use the coarsest separator that actually occurs in the text.
    separator, finer_separators = separators[-1], ()
    for index, candidate in enumerate(separators):
        if candidate == "" or candidate in text:
            separator, finer_separators = candidate, separators[index + 1:]
            break

    pieces = text.split(separator) if separator else list(text)

    chunks: list[str] = []
    fitting: list[str] = []
    for piece in pieces:
        if not piece:
            continue
        if len(piece) <= chunk_size:
            fitting.append(piece)
            continue
        # Too long: flush what we have, then split this piece more finely.
        if fitting:
            chunks.extend(_merge(fitting, separator, chunk_size, overlap_size))
            fitting = []
        chunks.extend(_split(piece, finer_separators, chunk_size, overlap_size))

    if fitting:
        chunks.extend(_merge(fitting, separator, chunk_size, overlap_size))
    return chunks


def _merge(pieces: list[str], separator: str, chunk_size: int,
           overlap_size: int) -> list[str]:
    """Greedily join pieces into chunks, carrying a tail of each chunk over."""
    chunks: list[str] = []
    current: deque[str] = deque()
    length = 0  # len(separator.join(current)), tracked incrementally
    sep_len = len(separator)

    for piece in pieces:
        if current and length + sep_len + len(piece) > chunk_size:
            chunks.append(separator.join(current))
            # Keep only as much of the tail as fits the overlap and leaves
            # room for the next piece.
            while current and (
                length > overlap_size
                or length + sep_len + len(piece) > chunk_size
            ):
                removed = current.popleft()
                length -= len(removed) + (sep_len if current else 0)
        length += len(piece) + (sep_len if current else 0)
        current.append(piece)

    if current:
        chunks.append(separator.join(current))
    return chunks
