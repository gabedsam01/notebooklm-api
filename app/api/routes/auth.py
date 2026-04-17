from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_auth_service, get_notebook_service
from app.models.auth import (
    AuthStatusResponse,
    LoginCompleteRequest,
    LoginCompleteResponse,
    LoginStartResponse,
    StorageStatePayload,
    StorageStateSaveResponse,
)
from app.services.notebooklm_auth_service import NotebookLMAuthService
from app.services.notebooklm_service import NotebookLMService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/status", response_model=AuthStatusResponse)
async def auth_status(
    auth_service: NotebookLMAuthService = Depends(get_auth_service),
    notebook_service: NotebookLMService = Depends(get_notebook_service),
) -> AuthStatusResponse:
    return await auth_service.get_status(notebook_service)


@router.post("/storage-state", response_model=StorageStateSaveResponse)
async def save_storage_state(
    payload: StorageStatePayload,
    auth_service: NotebookLMAuthService = Depends(get_auth_service),
) -> StorageStateSaveResponse:
    try:
        return auth_service.save_storage_state(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/login/start", response_model=LoginStartResponse)
async def login_start(
    auth_service: NotebookLMAuthService = Depends(get_auth_service),
) -> LoginStartResponse:
    return auth_service.start_login_flow()


@router.post("/login/complete", response_model=LoginCompleteResponse)
async def login_complete(
    payload: LoginCompleteRequest,
    auth_service: NotebookLMAuthService = Depends(get_auth_service),
) -> LoginCompleteResponse:
    response = auth_service.complete_login_flow(payload)
    if not response.completed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=response.detail)
    return response
