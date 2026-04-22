from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, Query, Request
from typing import cast

from app.core.config import Settings
from app.models.account import AccountResponse
from app.services.account_auth_service import AccountAuthService
from app.services.account_registry_service import AccountRegistryService
from app.services.artifact_service import ArtifactService
from app.services.job_service import JobService
from app.services.notebook_catalog_service import NotebookCatalogService
from app.services.notebook_repository import NotebookRepository
from app.services.notebooklm_factory import NotebookLMServiceFactory
from app.services.notebooklm_service import NotebookLMService
from app.services.source_builder_service import SourceBuilderService
from app.services.storage_state_service import StorageStateService


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_storage_state_service(request: Request) -> StorageStateService:
    return request.app.state.storage_state_service


def get_job_service(request: Request) -> JobService:
    return request.app.state.job_service


def get_auth_service(request: Request) -> AccountAuthService:
    return request.app.state.auth_service


def get_source_builder_service(request: Request) -> SourceBuilderService:
    return request.app.state.source_builder_service


def get_artifact_service(request: Request) -> ArtifactService:
    return request.app.state.artifact_service


def get_notebook_repository(request: Request) -> NotebookRepository:
    return request.app.state.notebook_repository


def get_account_registry(request: Request) -> AccountRegistryService:
    return request.app.state.account_registry


def get_service_factory(request: Request) -> NotebookLMServiceFactory:
    return request.app.state.service_factory


def get_current_account(
    request: Request,
    x_notebooklm_account_id: Annotated[str | None, Header()] = None,
    account_id: str | None = Query(default=None),
    registry: AccountRegistryService = Depends(get_account_registry),
) -> AccountResponse:
    _ = request
    target_id = x_notebooklm_account_id or account_id
    if target_id:
        account = registry.get_account(target_id)
        if account is None:
            raise HTTPException(status_code=404, detail="Account not found")
        return account
    return registry.get_default_account()


def get_notebook_service(
    account: AccountResponse = Depends(get_current_account),
    factory: NotebookLMServiceFactory = Depends(get_service_factory),
) -> NotebookLMService:
    return factory.get_service(account.id)


def get_notebook_catalog_service(
    account: AccountResponse = Depends(get_current_account),
    request: Request = None,
) -> NotebookCatalogService:
    req = cast(Request, request)
    return NotebookCatalogService(
        repository=req.app.state.notebook_repository,
        notebook_service=req.app.state.service_factory.get_service(account.id),
        account_id=account.id,
    )
