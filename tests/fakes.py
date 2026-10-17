"""In-memory implementations of the domain repository interfaces.

They let service tests run without a database. Changes are visible
immediately (there are no real transactions); tests check ``commits``
to verify the service committed its work.
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from itertools import count

from mini_rag.domain.models import Chunk, FileRecord, Project


class FakeProjects:

    def __init__(self):
        self.by_name: dict[str, Project] = {}
        self._ids = count(1)

    async def get_by_name(self, name: str) -> Project | None:
        return self.by_name.get(name)

    async def get_or_create(self, name: str) -> Project:
        if name not in self.by_name:
            self.by_name[name] = Project(id=next(self._ids), name=name, created_at=datetime.now(UTC))
        return self.by_name[name]


class FakeFiles:

    def __init__(self):
        self.records: list[FileRecord] = []
        self._ids = count(1)
        self.fail_with: Exception | None = None

    async def add(self, *, project_id, key, original_name, content_type, size_bytes) -> FileRecord:
        if self.fail_with:
            raise self.fail_with
        record = FileRecord(id=next(self._ids), project_id=project_id, key=key,
                            original_name=original_name, content_type=content_type,
                            size_bytes=size_bytes, created_at=datetime.now(UTC))
        self.records.append(record)
        return record

    async def get_by_key(self, project_id: int, key: str) -> FileRecord | None:
        return next((r for r in self.records if r.project_id == project_id and r.key == key), None)

    async def list_for_project(self, project_id: int, *, offset: int, limit: int) -> list[FileRecord]:
        return [r for r in self.records if r.project_id == project_id][offset:offset + limit]

    async def count_for_project(self, project_id: int) -> int:
        return sum(r.project_id == project_id for r in self.records)


class FakeChunks:

    def __init__(self):
        self.by_file: dict[int, list[Chunk]] = {}
        self.project_of_file: dict[int, int] = {}

    async def replace_for_file(self, file: FileRecord, chunks: Sequence[Chunk]) -> None:
        self.by_file[file.id] = list(chunks)
        self.project_of_file[file.id] = file.project_id

    async def list_for_file(self, file_id: int, *, offset: int, limit: int) -> list[Chunk]:
        chunks = sorted(self.by_file.get(file_id, []), key=lambda c: c.index)
        return chunks[offset:offset + limit]

    async def count_for_file(self, file_id: int) -> int:
        return len(self.by_file.get(file_id, []))

    async def count_for_project(self, project_id: int) -> int:
        return sum(len(chunks) for file_id, chunks in self.by_file.items()
                   if self.project_of_file[file_id] == project_id)


class FakeUnitOfWork:

    def __init__(self):
        self.projects = FakeProjects()
        self.files = FakeFiles()
        self.chunks = FakeChunks()
        self.commits = 0
        self.fail_commit_with: Exception | None = None

    async def commit(self) -> None:
        if self.fail_commit_with:
            raise self.fail_commit_with
        self.commits += 1

    async def rollback(self) -> None:
        pass
