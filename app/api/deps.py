from __future__ import annotations

from fastapi import Request

from app.core.config import Settings
from app.services.artifact_service import ArtifactService
from app.services.job_service import JobService
from app.services.notebook_catalog_service import NotebookCatalogService
from app.services.notebook_repository import NotebookRepository
from app.services.notebooklm_auth_service import NotebookLMAuthService
from app.services.notebooklm_service import NotebookLMService
from app.services.source_builder_service import SourceBuilderService
from app.services.storage_state_service import StorageStateService


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_storage_state_service(request: Request) -> StorageStateService:
    return request.app.state.storage_state_service


def get_notebook_service(request: Request) -> NotebookLMService:
    return request.app.state.notebook_service


def get_job_service(request: Request) -> JobService:
    return request.app.state.job_service


def get_auth_service(request: Request) -> NotebookLMAuthService:
    return request.app.state.auth_service


def get_source_builder_service(request: Request) -> SourceBuilderService:
    return request.app.state.source_builder_service


def get_artifact_service(request: Request) -> ArtifactService:
    return request.app.state.artifact_service


def get_notebook_repository(request: Request) -> NotebookRepository:
    return request.app.state.notebook_repository


def get_notebook_catalog_service(request: Request) -> NotebookCatalogService:
    return request.app.state.notebook_catalog_service
