from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_account, get_notebook_catalog_service, get_notebook_service
from app.models.account import AccountResponse
from app.models.notebooks import (
    NotebookCreateRequest,
    NotebookDeleteResultResponse,
    NotebookListResponse,
    NotebookResponse,
    NotebookSyncResponse,
)
from app.services.notebook_catalog_service import NotebookCatalogService
from app.services.notebooklm_service import NotebookLMService

router = APIRouter(prefix="/notebooks", tags=["notebooks"])


@router.post("", response_model=NotebookResponse, status_code=status.HTTP_201_CREATED)
async def create_notebook(
    payload: NotebookCreateRequest,
    notebook_service: NotebookLMService = Depends(get_notebook_service),
    notebook_catalog: NotebookCatalogService = Depends(get_notebook_catalog_service),
    account: AccountResponse = Depends(get_current_account),
) -> NotebookResponse:
    await _ensure_access(notebook_service)
    return await notebook_catalog.create_and_persist(payload.title)


@router.get("", response_model=NotebookListResponse)
async def list_notebooks(
    notebook_catalog: NotebookCatalogService = Depends(get_notebook_catalog_service),
) -> NotebookListResponse:
    items = notebook_catalog.list_persisted()
    return NotebookListResponse(count=len(items), items=items)


@router.post("/sync", response_model=NotebookSyncResponse)
async def sync_notebooks(
    notebook_service: NotebookLMService = Depends(get_notebook_service),
    notebook_catalog: NotebookCatalogService = Depends(get_notebook_catalog_service),
) -> NotebookSyncResponse:
    await _ensure_access(notebook_service)
    return await notebook_catalog.sync_from_account()


@router.get("/{notebook_id}", response_model=NotebookResponse)
async def get_notebook(
    notebook_id: str,
    notebook_service: NotebookLMService = Depends(get_notebook_service),
    notebook_catalog: NotebookCatalogService = Depends(get_notebook_catalog_service),
) -> NotebookResponse:
    await _ensure_access(notebook_service)
    notebook = await notebook_catalog.refresh_and_get(notebook_id)
    if notebook is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notebook nao encontrado")
    return notebook


@router.delete("/{notebook_id}", response_model=NotebookDeleteResultResponse)
async def delete_notebook(
    notebook_id: str,
    notebook_catalog: NotebookCatalogService = Depends(get_notebook_catalog_service),
) -> NotebookDeleteResultResponse:
    return await notebook_catalog.delete_notebook(notebook_id=notebook_id)


@router.delete("/local/{local_id}", response_model=NotebookDeleteResultResponse)
async def delete_notebook_by_local_id(
    local_id: int,
    notebook_catalog: NotebookCatalogService = Depends(get_notebook_catalog_service),
) -> NotebookDeleteResultResponse:
    return await notebook_catalog.delete_notebook(local_id=local_id)


async def _ensure_access(notebook_service: NotebookLMService) -> None:
    access = await notebook_service.verify_access()
    if not access.ok:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=access.detail)
