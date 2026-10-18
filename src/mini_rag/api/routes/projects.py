from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from mini_rag.api.dependencies import DeletionServiceDep, ProjectServiceDep
from mini_rag.api.schemas import (
    ChunkListResponse,
    ChunkResponse,
    FileIdPath,
    FileListResponse,
    FileResponse,
    Pagination,
    ProjectId,
    ProjectListItem,
    ProjectListResponse,
    ProjectResponse,
    ProjectUsageResponse,
    error_responses,
)
from mini_rag.core.errors import FileNotFound, ProjectNotFound
from mini_rag.domain.models import FileRecord

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])

PaginationDep = Annotated[Pagination, Depends()]


def _file_response(record: FileRecord) -> FileResponse:
    return FileResponse(file_id=record.key, original_name=record.original_name,
                        content_type=record.content_type, size_bytes=record.size_bytes,
                        created_at=record.created_at)


@router.get("", summary="List projects in name order")
async def list_projects(page: PaginationDep, service: ProjectServiceDep) -> ProjectListResponse:
    result = await service.list_projects(offset=page.offset, limit=page.limit)
    return ProjectListResponse(
        total=result.total, offset=result.offset, limit=result.limit,
        items=[ProjectListItem(name=project.name, created_at=project.created_at)
               for project in result.items])


@router.get("/{project_id}", summary="Project details with file, chunk and index counts",
            responses=error_responses(ProjectNotFound))
async def get_project(project_id: ProjectId, service: ProjectServiceDep) -> ProjectResponse:
    summary = await service.get_summary(project_id)
    return ProjectResponse(name=summary.project.name, created_at=summary.project.created_at,
                           files_count=summary.files_count, chunks_count=summary.chunks_count,
                           embedded_chunks_count=summary.embedded_chunks_count)


@router.get("/{project_id}/usage", summary="Token usage and cost of the project's answers",
            responses=error_responses(ProjectNotFound))
async def get_usage(project_id: ProjectId, service: ProjectServiceDep) -> ProjectUsageResponse:
    totals = await service.get_usage(project_id)
    return ProjectUsageResponse(answers=totals.answers, answered=totals.answered,
                                input_tokens=totals.input_tokens,
                                output_tokens=totals.output_tokens, cost_usd=totals.cost_usd,
                                unpriced_answers=totals.unpriced_answers)


@router.get("/{project_id}/files", summary="List a project's files in upload order",
            responses=error_responses(ProjectNotFound))
async def list_files(project_id: ProjectId, page: PaginationDep,
                     service: ProjectServiceDep) -> FileListResponse:
    result = await service.list_files(project_id, offset=page.offset, limit=page.limit)
    return FileListResponse(total=result.total, offset=result.offset, limit=result.limit,
                            items=[_file_response(record) for record in result.items])


@router.get("/{project_id}/files/{file_id}/chunks", summary="List a file's chunks in order",
            responses=error_responses(ProjectNotFound, FileNotFound))
async def list_chunks(project_id: ProjectId, file_id: FileIdPath, page: PaginationDep,
                      service: ProjectServiceDep) -> ChunkListResponse:
    result = await service.list_chunks(project_id, file_id, offset=page.offset, limit=page.limit)
    return ChunkListResponse(
        total=result.total, offset=result.offset, limit=result.limit,
        items=[ChunkResponse(chunk_index=chunk.index, text=chunk.text, metadata=chunk.metadata)
               for chunk in result.items])


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Delete a project with all its files, chunks, answers and conversations",
               responses=error_responses(ProjectNotFound))
async def delete_project(project_id: ProjectId, service: DeletionServiceDep) -> Response:
    await service.delete_project(project_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{project_id}/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Delete a file with its chunks",
               description="Answers that cited the file keep their copy of the cited text.",
               responses=error_responses(ProjectNotFound, FileNotFound))
async def delete_file(project_id: ProjectId, file_id: FileIdPath,
                      service: DeletionServiceDep) -> Response:
    await service.delete_file(project_id, file_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
