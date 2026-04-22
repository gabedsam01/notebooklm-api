from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.routes import accounts, artifacts, auth, health, jobs, notebooks, operations, sources
from app.services.notebook_catalog_service import NotebookCatalogService
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.services.account_auth_service import AccountAuthService
from app.services.account_keepalive_service import AccountKeepaliveService
from app.services.account_registry_service import AccountRegistryService
from app.services.artifact_service import ArtifactService
from app.services.job_repository import LocalJsonJobRepository
from app.services.job_service import JobService
from app.services.notebook_repository import NotebookRepository
from app.services.notebooklm_factory import NotebookLMServiceFactory
from app.services.source_builder_service import SourceBuilderService
from app.services.storage_state_service import StorageStateService
from app.web import routes as web_routes

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)

    _prepare_directories(resolved_settings)
    _sync_notebooklm_home(resolved_settings)

    storage_state_service = StorageStateService(resolved_settings.storage_state_path)
    account_registry = AccountRegistryService(resolved_settings)
    account_registry.ensure_default_account()
    service_factory = NotebookLMServiceFactory(settings=resolved_settings, registry=account_registry)
    auth_service = AccountAuthService(registry=account_registry)
    source_builder_service = SourceBuilderService()
    artifact_service = ArtifactService(resolved_settings.artifacts_dir)
    notebook_repository = NotebookRepository(resolved_settings.sqlite_db_path)
    default_notebook_catalog_service = NotebookCatalogService(
        repository=notebook_repository,
        notebook_service=service_factory.get_service(account_registry.default_account_id),
        account_id=account_registry.default_account_id,
    )
    job_repository = LocalJsonJobRepository(resolved_settings.jobs_dir)
    job_service = JobService(
        settings=resolved_settings,
        repository=job_repository,
        notebook_service_factory=service_factory,
        notebook_repository=notebook_repository,
        source_builder=source_builder_service,
        artifact_service=artifact_service,
    )
    keepalive_service = AccountKeepaliveService(
        settings=resolved_settings,
        registry=account_registry,
        service_factory=service_factory,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        await keepalive_service.start()
        yield
        await keepalive_service.shutdown()
        await job_service.shutdown()

    app = FastAPI(
        title=resolved_settings.app_name,
        version=resolved_settings.app_version,
        lifespan=lifespan,
    )

    app.state.settings = resolved_settings
    app.state.storage_state_service = storage_state_service
    app.state.account_registry = account_registry
    app.state.service_factory = service_factory
    app.state.auth_service = auth_service
    app.state.source_builder_service = source_builder_service
    app.state.artifact_service = artifact_service
    app.state.notebook_repository = notebook_repository
    app.state.notebook_catalog_service = default_notebook_catalog_service
    app.state.notebook_service = service_factory.get_service(account_registry.default_account_id)
    app.state.job_service = job_service
    app.state.keepalive_service = keepalive_service
    app.state.templates = Jinja2Templates(directory=str(resolved_settings.templates_dir))

    app.mount("/static", StaticFiles(directory=str(resolved_settings.static_dir)), name="static")

    app.include_router(health.router)
    app.include_router(accounts.router)
    app.include_router(auth.router)
    app.include_router(jobs.router)
    app.include_router(notebooks.router)
    app.include_router(sources.router)
    app.include_router(operations.router)
    app.include_router(artifacts.router)
    app.include_router(web_routes.router)

    return app


def _prepare_directories(settings: Settings) -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.jobs_dir.mkdir(parents=True, exist_ok=True)
    settings.artifacts_dir.mkdir(parents=True, exist_ok=True)
    settings.temp_dir.mkdir(parents=True, exist_ok=True)
    settings.storage_state_path.parent.mkdir(parents=True, exist_ok=True)
    settings.accounts_dir.mkdir(parents=True, exist_ok=True)
    settings.sqlite_db_path.parent.mkdir(parents=True, exist_ok=True)
    settings.templates_dir.mkdir(parents=True, exist_ok=True)
    settings.static_dir.mkdir(parents=True, exist_ok=True)


def _sync_notebooklm_home(settings: Settings) -> None:
    auth_dir = str(settings.storage_state_path.parent)
    os.environ["NOTEBOOKLM_HOME"] = auth_dir
    logger.info("NOTEBOOKLM_HOME sincronizado: %s", auth_dir)


app = create_app()
