from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_notebook_catalog_service, get_notebook_service, get_source_builder_service
from app.models.sources import (
    AddBatchTextSourcesRequest,
    AddSingleTextSourceRequest,
    SourceMutationResponse,
)
from app.services.notebook_catalog_service import NotebookCatalogService
from app.services.notebooklm_service import NotebookLMService
from app.services.source_builder_service import SourceBuilderService

router = APIRouter(prefix="/sources", tags=["sources"])


@router.post("/text", response_model=SourceMutationResponse)
async def add_text_source(
    payload: AddSingleTextSourceRequest,
    notebook_service: NotebookLMService = Depends(get_notebook_service),
    notebook_catalog: NotebookCatalogService = Depends(get_notebook_catalog_service),
    source_builder: SourceBuilderService = Depends(get_source_builder_service),
) -> SourceMutationResponse:
    await _ensure_access(notebook_service)
    resolved = notebook_catalog.resolve_notebook_id(payload.notebook_id, payload.local_id)
    source = source_builder.normalize_single(payload.title, payload.content)
    source_id = await notebook_service.add_text_source(
        notebook_id=resolved.notebook_id,
        title=source.title,
        content=source.content,
    )
    await notebook_catalog.refresh_and_get(resolved.notebook_id)
    return SourceMutationResponse(
        notebook_id=resolved.notebook_id,
        added_count=1,
        source_ids=[source_id] if source_id else [],
    )


@router.post("/batch", response_model=SourceMutationResponse)
async def add_text_sources_batch(
    payload: AddBatchTextSourcesRequest,
    notebook_service: NotebookLMService = Depends(get_notebook_service),
    notebook_catalog: NotebookCatalogService = Depends(get_notebook_catalog_service),
    source_builder: SourceBuilderService = Depends(get_source_builder_service),
) -> SourceMutationResponse:
    await _ensure_access(notebook_service)
    resolved = notebook_catalog.resolve_notebook_id(payload.notebook_id, payload.local_id)
    normalized = source_builder.normalize_batch(payload.sources)
    source_ids = await notebook_service.add_text_sources_batch(
        notebook_id=resolved.notebook_id,
        sources=[item.model_dump() for item in normalized],
    )
    await notebook_catalog.refresh_and_get(resolved.notebook_id)
    return SourceMutationResponse(
        notebook_id=resolved.notebook_id,
        added_count=len(normalized),
        source_ids=source_ids,
    )


async def _ensure_access(notebook_service: NotebookLMService) -> None:
    access = await notebook_service.verify_access()
    if not access.ok:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=access.detail)
