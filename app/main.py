from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.routes import artifacts, auth, health, jobs, notebooks, operations, sources
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.services.artifact_service import ArtifactService
from app.services.job_repository import LocalJsonJobRepository
from app.services.job_service import JobService
from app.services.notebook_catalog_service import NotebookCatalogService
from app.services.notebook_repository import NotebookRepository
from app.services.notebooklm_auth_service import NotebookLMAuthService
from app.services.notebooklm_service import build_notebook_service
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
    notebook_service = build_notebook_service(
        settings=resolved_settings,
        storage_state_service=storage_state_service,
    )
    auth_service = NotebookLMAuthService(storage_state_service=storage_state_service)
    source_builder_service = SourceBuilderService()
    artifact_service = ArtifactService(resolved_settings.artifacts_dir)
    notebook_repository = NotebookRepository(resolved_settings.sqlite_db_path)
    notebook_catalog_service = NotebookCatalogService(
        repository=notebook_repository,
        notebook_service=notebook_service,
    )
    job_repository = LocalJsonJobRepository(resolved_settings.jobs_dir)
    job_service = JobService(
        settings=resolved_settings,
        repository=job_repository,
        notebook_service=notebook_service,
        source_builder=source_builder_service,
        artifact_service=artifact_service,
        notebook_catalog=notebook_catalog_service,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        await job_service.shutdown()

    app = FastAPI(
        title=resolved_settings.app_name,
        version=resolved_settings.app_version,
        lifespan=lifespan,
    )

    app.state.settings = resolved_settings
    app.state.storage_state_service = storage_state_service
    app.state.notebook_service = notebook_service
    app.state.auth_service = auth_service
    app.state.source_builder_service = source_builder_service
    app.state.artifact_service = artifact_service
    app.state.notebook_repository = notebook_repository
    app.state.notebook_catalog_service = notebook_catalog_service
    app.state.job_service = job_service
    app.state.templates = Jinja2Templates(directory=str(resolved_settings.templates_dir))

    app.mount("/static", StaticFiles(directory=str(resolved_settings.static_dir)), name="static")

    app.include_router(health.router)
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
    settings.sqlite_db_path.parent.mkdir(parents=True, exist_ok=True)
    settings.templates_dir.mkdir(parents=True, exist_ok=True)
    settings.static_dir.mkdir(parents=True, exist_ok=True)


def _sync_notebooklm_home(settings: Settings) -> None:
    """Sincroniza NOTEBOOKLM_HOME com o diretório de auth do app.

    A lib notebooklm-py usa ``load_httpx_cookies()`` sem argumento de path
    durante downloads de artefatos (``download_audio``/``download_video``).
    Internamente, essa função resolve o ``storage_state.json`` via
    ``get_storage_path()`` → ``$NOTEBOOKLM_HOME/storage_state.json``.

    Sem esta sincronização, o download tenta ler cookies de
    ``~/.notebooklm/storage_state.json`` em vez de
    ``data/auth/storage_state.json`` (onde o app efetivamente salva).
    """
    auth_dir = str(settings.storage_state_path.parent)
    os.environ["NOTEBOOKLM_HOME"] = auth_dir
    logger.info("NOTEBOOKLM_HOME sincronizado: %s", auth_dir)


app = create_app()
