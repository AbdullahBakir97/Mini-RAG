import pytest
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError

from mini_rag.domain.models import Chunk
from mini_rag.persistence.database import create_engine, create_session_factory
from mini_rag.persistence.repositories import SqlUnitOfWork
from mini_rag.persistence.tables import ProjectRow

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
