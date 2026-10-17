import pytest
from sqlalchemy import delete, text
from sqlalchemy.exc import IntegrityError

from mini_rag.domain.models import Chunk
from mini_rag.persistence.database import create_engine, create_session_factory
from mini_rag.persistence.repositories import SqlUnitOfWork
from mini_rag.persistence.tables import EMBEDDING_DIMENSIONS, ProjectRow

pytestmark = pytest.mark.anyio


@pytest.fixture
async def session_factory(db):
    engine = create_engine(db)
    yield create_session_factory(engine)
    await engine.dispose()


@pytest.fixture
async def uow(session_factory):
    async with session_factory() as session:
        yield SqlUnitOfWork(session)


async def add_file(uow, project, key="abc_notes.txt", size=10):
    return await uow.files.add(project_id=project.id, key=key, original_name="notes.txt",
                               content_type="text/plain", size_bytes=size)


def vector(*head: float) -> list[float]:
    """A full-length embedding that starts with ``head`` and is zero after it."""
    return [*head, *[0.0] * (EMBEDDING_DIMENSIONS - len(head))]


async def embed_all(uow, project, vectors_by_text: dict[str, list[float]]):
    pending = await uow.chunks.list_unembedded(project.id, file_id=None, limit=100)
    await uow.chunks.set_embeddings(
        {chunk.id: vectors_by_text[chunk.text] for chunk in pending if chunk.text in vectors_by_text})


async def test_get_or_create_project_is_idempotent(uow):
    first = await uow.projects.get_or_create("demo")
    second = await uow.projects.get_or_create("demo")

    assert first == second
    assert first.name == "demo" and first.created_at is not None
    assert await uow.projects.get_by_name("other") is None


async def test_add_and_get_file(uow):
    project = await uow.projects.get_or_create("demo")

    added = await add_file(uow, project, size=1234)

    assert added.id > 0 and added.size_bytes == 1234 and added.created_at is not None
    assert await uow.files.get_by_key(project.id, "abc_notes.txt") == added
    assert await uow.files.get_by_key(project.id, "missing.txt") is None


async def test_file_keys_are_unique_per_project(uow):
    first = await uow.projects.get_or_create("a")
    second = await uow.projects.get_or_create("b")
    await add_file(uow, first)
    await add_file(uow, second)  # same key, other project: fine

    with pytest.raises(IntegrityError):
        await add_file(uow, first)


async def test_files_are_listed_in_upload_order_with_paging(uow):
    project = await uow.projects.get_or_create("demo")
    keys = [f"k{i}_f.txt" for i in range(5)]
    for key in keys:
        await add_file(uow, project, key=key)

    page = await uow.files.list_for_project(project.id, offset=1, limit=2)

    assert [f.key for f in page] == keys[1:3]
    assert await uow.files.count_for_project(project.id) == 5


async def test_replace_chunks_for_file(uow):
    project = await uow.projects.get_or_create("demo")
    file = await add_file(uow, project)
    await uow.chunks.replace_for_file(file, [Chunk(i, f"old {i}") for i in range(3)])

    new = [Chunk(0, "new 0", {"page": 1}), Chunk(1, "new 1", {"page": 2})]
    await uow.chunks.replace_for_file(file, new)

    assert await uow.chunks.list_for_file(file.id, offset=0, limit=10) == new
    assert await uow.chunks.count_for_file(file.id) == 2
    assert await uow.chunks.count_for_project(project.id) == 2


async def test_chunks_are_listed_by_index_with_paging(uow):
    project = await uow.projects.get_or_create("demo")
    file = await add_file(uow, project)
    await uow.chunks.replace_for_file(file, [Chunk(i, f"c{i}") for i in reversed(range(5))])

    page = await uow.chunks.list_for_file(file.id, offset=2, limit=2)

    assert [c.index for c in page] == [2, 3]


async def test_deleting_a_project_cascades_to_files_and_chunks(uow):
    project = await uow.projects.get_or_create("demo")
    file = await add_file(uow, project)
    await uow.chunks.replace_for_file(file, [Chunk(0, "text")])

    await uow.session.execute(delete(ProjectRow).where(ProjectRow.id == project.id))

    assert await uow.files.count_for_project(project.id) == 0
    assert await uow.chunks.count_for_file(file.id) == 0


async def test_uncommitted_work_is_discarded_and_commit_persists(session_factory):
    async with session_factory() as session:
        await SqlUnitOfWork(session).projects.get_or_create("discarded")
    async with session_factory() as session:
        uow = SqlUnitOfWork(session)
        await uow.projects.get_or_create("kept")
        await uow.commit()

    async with session_factory() as session:
        uow = SqlUnitOfWork(session)
        assert await uow.projects.get_by_name("discarded") is None
        assert await uow.projects.get_by_name("kept") is not None


async def test_unembedded_chunks_are_listed_oldest_first_until_embedded(uow):
    project = await uow.projects.get_or_create("demo")
    first = await add_file(uow, project, key="a_1.txt")
    second = await add_file(uow, project, key="b_2.txt")
    await uow.chunks.replace_for_file(first, [Chunk(0, "a0"), Chunk(1, "a1")])
    await uow.chunks.replace_for_file(second, [Chunk(0, "b0")])

    pending = await uow.chunks.list_unembedded(project.id, file_id=None, limit=10)
    assert [c.text for c in pending] == ["a0", "a1", "b0"]
    assert [c.text for c in await uow.chunks.list_unembedded(project.id, file_id=second.id, limit=10)] == ["b0"]
    assert len(await uow.chunks.list_unembedded(project.id, file_id=None, limit=2)) == 2

    await uow.chunks.set_embeddings({pending[0].id: vector(1.0), pending[2].id: vector(0.0, 1.0)})

    assert [c.text for c in await uow.chunks.list_unembedded(project.id, file_id=None, limit=10)] == ["a1"]
    assert await uow.chunks.count_embedded_for_project(project.id) == 2


async def test_set_embeddings_skips_chunks_deleted_meanwhile(uow):
    project = await uow.projects.get_or_create("demo")
    file = await add_file(uow, project)
    await uow.chunks.replace_for_file(file, [Chunk(0, "old")])
    [old] = await uow.chunks.list_unembedded(project.id, file_id=None, limit=10)
    await uow.chunks.replace_for_file(file, [Chunk(0, "new")])  # e.g. reprocessed

    await uow.chunks.set_embeddings({old.id: vector(1.0)})

    assert await uow.chunks.count_embedded_for_project(project.id) == 0


async def test_reprocessing_a_file_drops_its_embeddings(uow):
    project = await uow.projects.get_or_create("demo")
    file = await add_file(uow, project)
    await uow.chunks.replace_for_file(file, [Chunk(0, "text")])
    await embed_all(uow, project, {"text": vector(1.0)})

    await uow.chunks.replace_for_file(file, [Chunk(0, "text")])

    assert await uow.chunks.count_embedded_for_project(project.id) == 0


async def test_search_ranks_chunks_by_cosine_similarity(uow):
    project = await uow.projects.get_or_create("demo")
    file = await add_file(uow, project, key="k_doc.pdf")
    await uow.chunks.replace_for_file(file, [
        Chunk(0, "same", {"page": 1}), Chunk(1, "close", {"page": 2}),
        Chunk(2, "opposite"), Chunk(3, "not indexed")])
    await embed_all(uow, project, {
        "same": vector(1.0, 0.0), "close": vector(1.0, 1.0), "opposite": vector(-1.0, 0.0)})

    hits = await uow.chunks.search(project.id, vector(2.0, 0.0), top_k=10, min_score=None)

    assert [hit.chunk.text for hit in hits] == ["same", "close", "opposite"]
    assert [round(hit.score, 4) for hit in hits] == [1.0, 0.7071, -1.0]
    assert hits[0].file_key == "k_doc.pdf"
    assert hits[0].chunk == Chunk(0, "same", {"page": 1})


async def test_search_respects_top_k_and_min_score(uow):
    project = await uow.projects.get_or_create("demo")
    file = await add_file(uow, project)
    await uow.chunks.replace_for_file(file, [Chunk(0, "same"), Chunk(1, "close"), Chunk(2, "far")])
    await embed_all(uow, project, {
        "same": vector(1.0, 0.0), "close": vector(1.0, 1.0), "far": vector(0.0, 1.0)})
    query = vector(1.0, 0.0)

    top_two = await uow.chunks.search(project.id, query, top_k=2, min_score=None)
    above_half = await uow.chunks.search(project.id, query, top_k=10, min_score=0.5)

    assert [hit.chunk.text for hit in top_two] == ["same", "close"]
    assert [hit.chunk.text for hit in above_half] == ["same", "close"]


async def test_search_stays_within_the_project(uow):
    mine = await uow.projects.get_or_create("mine")
    other = await uow.projects.get_or_create("other")
    for project, chunk_text in [(mine, "my text"), (other, "their text")]:
        file = await add_file(uow, project)
        await uow.chunks.replace_for_file(file, [Chunk(0, chunk_text)])
        await embed_all(uow, project, {chunk_text: vector(1.0)})

    hits = await uow.chunks.search(mine.id, vector(1.0), top_k=10, min_score=None)

    assert [hit.chunk.text for hit in hits] == ["my text"]
    assert await uow.chunks.search(other.id + 100, vector(1.0), top_k=10, min_score=None) == []


async def test_search_finds_top_k_even_when_most_neighbours_belong_to_other_projects(uow):
    # Without an iterative index scan, the HNSW index would return its
    # nearest candidates (all from "crowd") and the project filter would
    # leave nothing.
    crowd = await uow.projects.get_or_create("crowd")
    small = await uow.projects.get_or_create("small")
    crowd_file = await add_file(uow, crowd)
    await uow.chunks.replace_for_file(crowd_file, [Chunk(i, f"crowd {i}") for i in range(300)])
    await embed_all(uow, crowd, {f"crowd {i}": vector(1.0, i / 1000) for i in range(300)})
    small_file = await add_file(uow, small)
    await uow.chunks.replace_for_file(small_file, [Chunk(0, "mine 0"), Chunk(1, "mine 1")])
    await embed_all(uow, small, {"mine 0": vector(0.0, 1.0), "mine 1": vector(0.1, 1.0)})
    # Force the HNSW index, as the planner would choose for a large table.
    # The test never commits, so this is rolled back.
    await uow.session.execute(text("DROP INDEX ix_chunks_project_id"))
    await uow.session.execute(text("SET LOCAL enable_seqscan = off"))

    hits = await uow.chunks.search(small.id, vector(1.0, 0.0), top_k=2, min_score=None)

    assert [hit.chunk.text for hit in hits] == ["mine 1", "mine 0"]
