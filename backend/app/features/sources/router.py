from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.exceptions import DuplicateRecordError, RecordNotFoundError
from app.features.sources.schemas import (
    SourceCreateSchema,
    SourceListSchema,
    SourceResponseSchema,
    SourceUpdateSchema,
)
from app.features.sources.service import SourceService
from app.shared.dependencies import get_source_service

router = APIRouter(prefix="/sources", tags=["Sources"])


@router.get(
    "",
    response_model=SourceListSchema,
    summary="List registered news sources",
)
async def list_sources(
    language: str | None = Query(
        None, description="Filter by language code (e.g. 'bn', 'en')"
    ),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    size: int = Query(20, ge=1, le=100, description="Results per page"),
    service: SourceService = Depends(get_source_service),
) -> SourceListSchema:
    return await service.list_sources(language=language, page=page, size=size)


@router.post(
    "",
    response_model=SourceResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new news source",
)
async def create_source(
    payload: SourceCreateSchema,
    service: SourceService = Depends(get_source_service),
) -> SourceResponseSchema:
    try:
        return await service.create_source(payload)
    except DuplicateRecordError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "duplicate_source", "message": exc.message},
        ) from exc


@router.get(
    "/{source_id}",
    response_model=SourceResponseSchema,
    summary="Get a source by UUID",
)
async def get_source(
    source_id: uuid.UUID,
    service: SourceService = Depends(get_source_service),
) -> SourceResponseSchema:
    try:
        return await service.get_source(source_id)
    except RecordNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": exc.message},
        ) from exc


@router.put(
    "/{source_id}",
    response_model=SourceResponseSchema,
    summary="Update a source (partial update — only provided fields are changed)",
)
async def update_source(
    source_id: uuid.UUID,
    payload: SourceUpdateSchema,
    service: SourceService = Depends(get_source_service),
) -> SourceResponseSchema:
    try:
        return await service.update_source(source_id, payload)
    except RecordNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": exc.message},
        ) from exc


@router.delete(
    "/{source_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a source",
)
async def delete_source(
    source_id: uuid.UUID,
    service: SourceService = Depends(get_source_service),
) -> None:
    try:
        await service.delete_source(source_id)
    except RecordNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": exc.message},
        ) from exc
