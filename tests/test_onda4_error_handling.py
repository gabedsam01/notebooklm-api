"""Onda 4 - excecoes e respostas HTTP seguras.

TDD: escritos ANTES da implementacao. Sem sessao real do Google.

- Mapeamento excecao -> (status, code) via exception_mapper (unit).
- Sanitizacao: envelope publico nunca contem segredo/path/traceback.
- Rotas/web/jobs: erro do adapter vira envelope; job.error e web nao vazam cru.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from notebooklm.exceptions import (
    ArtifactFeatureUnavailableError,
    ArtifactNotReadyError,
    AuthError,
    DecodingError,
    NetworkError,
    NotebookLimitError,
    NotebookLMError,
    NotFoundError,
    RateLimitError,
    RPCError,
    RPCTimeoutError,
    ServerError,
    UnknownRPCMethodError,
    ValidationError,
    WaitTimeoutError,
)

from app.core.config import Settings
from app.services.notebooklm_service import MockNotebookLMService, NotebookLMOperationError
from app.utils.error_sanitizer import sanitize_exception

SECRET = "cookie SID=topsecret __Secure-1PSIDTS=zzz Bearer abc.def at /home/u/data/accounts/acc/chrome-profile/storage_state.json"
FORBIDDEN = [
    "storage_state",
    "cookie",
    "Authorization",
    "Bearer",
    "SID",
    "__Secure-1PSID",
    "__Secure-1PSIDTS",
    "/home/",
    "/app/",
    "/tmp/",
    "data/accounts",
    "traceback",
    "chrome-profile",
    "storage_state.json",
    "topsecret",
]


# =========================================================================
# Mapeamento excecao -> HTTP (unit no exception_mapper)
# =========================================================================

_CASES = [
    (NotFoundError("x"), 404, "NOT_FOUND"),
    (AuthError("x"), 401, "AUTH_REQUIRED"),
    (RateLimitError("x"), 429, "RATE_LIMITED"),
    (ValidationError("x"), 422, "VALIDATION_ERROR"),
    (WaitTimeoutError("x"), 504, "UPSTREAM_TIMEOUT"),
    (ArtifactNotReadyError("x"), 409, "NOT_READY"),
    (ArtifactFeatureUnavailableError("x"), 409, "FEATURE_UNAVAILABLE"),
    (NotebookLimitError("x"), 403, "QUOTA"),
    (UnknownRPCMethodError("x"), 502, "UPSTREAM_SCHEMA_DRIFT"),
    (DecodingError("x"), 502, "UPSTREAM_SCHEMA_DRIFT"),
    (ServerError("x"), 502, "UPSTREAM_ERROR"),
    (NetworkError("x"), 502, "UPSTREAM_NETWORK"),
    (RPCTimeoutError("x"), 502, "UPSTREAM_NETWORK"),
    (RPCError("x"), 502, "UPSTREAM_ERROR"),
    (NotebookLMError("x"), 502, "UPSTREAM_ERROR"),
    (ValueError("x"), 500, "INTERNAL_ERROR"),
    (NotebookLMOperationError("x"), 502, "UPSTREAM_ERROR"),
]


@pytest.mark.parametrize("exc,status_code,code", _CASES)
def test_mapping_status_and_code(exc, status_code, code) -> None:
    from app.services.exception_mapper import (
        map_exception_to_error_response,
        map_exception_to_http_status,
    )

    assert map_exception_to_http_status(exc) == status_code
    body = map_exception_to_error_response(exc)
    assert body.code == code
    assert body.error is True
    assert isinstance(body.message, str) and body.message


def test_mapping_unwraps_operation_error_cause() -> None:
    from app.services.exception_mapper import map_exception_to_http_status

    wrapped = NotebookLMOperationError("wrapper")
    wrapped.__cause__ = AuthError("secret")
    assert map_exception_to_http_status(wrapped) == 401


# =========================================================================
# Sanitizacao
# =========================================================================

def test_envelope_never_contains_secrets() -> None:
    from app.services.exception_mapper import map_exception_to_error_response

    body = map_exception_to_error_response(AuthError(SECRET))
    blob = body.model_dump_json()
    for token in FORBIDDEN:
        assert token not in blob


def test_envelope_has_consistent_shape() -> None:
    from app.models.errors import ErrorResponse
    from app.services.exception_mapper import map_exception_to_error_response

    body = map_exception_to_error_response(RPCError("x"))
    assert isinstance(body, ErrorResponse)
    assert set(body.model_dump()) == {"error", "code", "message", "detail"}
    assert body.error is True
    assert body.detail is None


def test_sanitizer_strips_all_forbidden_tokens() -> None:
    out = sanitize_exception(Exception(SECRET + "\nTraceback (most recent call last): boom"))
    for token in FORBIDDEN:
        assert token not in out, f"vazou: {token} em {out!r}"


def test_sanitizer_keeps_useful_class_name() -> None:
    out = sanitize_exception(AuthError("cookie SID=topsecret"))
    assert "AuthError" in out  # informacao util
    assert "topsecret" not in out
    assert "SID" not in out


# =========================================================================
# Handlers end-to-end (app isolado)
# =========================================================================

def _app_raising(exc: Exception) -> TestClient:
    from app.api.error_handlers import register_exception_handlers

    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom")
    async def boom():  # type: ignore[no-untyped-def]
        raise exc

    return TestClient(app, raise_server_exceptions=False)


def test_handler_known_exception_returns_safe_envelope() -> None:
    client = _app_raising(AuthError(SECRET))
    resp = client.get("/boom")
    assert resp.status_code == 401
    body = resp.json()
    assert body["error"] is True
    assert body["code"] == "AUTH_REQUIRED"
    for token in FORBIDDEN:
        assert token not in resp.text


def test_handler_unexpected_returns_500_without_traceback() -> None:
    client = _app_raising(ValueError("boom " + SECRET))
    resp = client.get("/boom")
    assert resp.status_code == 500
    assert resp.json()["code"] == "INTERNAL_ERROR"
    for token in FORBIDDEN + ["boom"]:
        assert token not in resp.text


# =========================================================================
# Rota real: erro do adapter -> envelope seguro
# =========================================================================

def _build_client(tmp_path: Path) -> TestClient:
    # paths absolutos do repo -> robusto a mudanca de CWD por outros testes
    # (ex.: test_cli faz os.chdir sem restaurar).
    repo = Path(__file__).resolve().parent.parent
    data = tmp_path / "data"
    settings = Settings(
        data_dir=data,
        jobs_dir=data / "jobs",
        artifacts_dir=data / "artifacts",
        temp_dir=data / "tmp",
        storage_state_path=data / "auth" / "storage_state.json",
        accounts_dir=data / "accounts",
        sqlite_db_path=data / "notebooks.db",
        templates_dir=repo / "app" / "templates",
        static_dir=repo / "app" / "static",
        notebooklm_mode="mock",
        worker_poll_interval_seconds=0.01,
    )
    return TestClient(create_app(settings), raise_server_exceptions=False)


from app.main import create_app  # noqa: E402  (after Settings import for clareza)


def test_adapter_error_in_route_returns_envelope(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        MockNotebookLMService,
        "verify_access",
        AsyncMock(side_effect=AuthError(SECRET)),
    )
    client = _build_client(tmp_path)
    resp = client.post("/notebooks", json={"title": "x"})
    assert resp.status_code == 401
    body = resp.json()
    assert body["error"] is True
    assert body["code"] == "AUTH_REQUIRED"
    for token in FORBIDDEN:
        assert token not in resp.text


# =========================================================================
# job_service: _background_download nao salva str(exc) cru
# =========================================================================

class _RaisingDownloadService:
    async def list_artifacts(self, notebook_id):  # type: ignore[no-untyped-def]
        return []

    async def download_artifact(self, **kwargs):  # type: ignore[no-untyped-def]
        raise Exception(SECRET)


class _Factory:
    def __init__(self, service):  # type: ignore[no-untyped-def]
        self._service = service

    def get_service(self, account_id):  # type: ignore[no-untyped-def]
        return self._service


def test_background_download_sanitizes_job_error(tmp_path: Path, monkeypatch) -> None:
    from app.services.artifact_service import ArtifactService
    from app.services.job_repository import LocalJsonJobRepository
    from app.services.job_service import JobService
    from app.services.notebook_repository import NotebookRepository
    from app.services.source_builder_service import SourceBuilderService
    from app.models.jobs import JobRecord, JobStatus, JobType

    # retries sem espera real
    monkeypatch.setattr("app.services.job_service.asyncio.sleep", AsyncMock())

    data = tmp_path / "data"
    settings = Settings(data_dir=data, jobs_dir=data / "jobs", artifacts_dir=data / "artifacts", temp_dir=data / "tmp", storage_state_path=data / "auth" / "storage_state.json", accounts_dir=data / "accounts", sqlite_db_path=data / "notebooks.db", notebooklm_mode="mock")
    repo = LocalJsonJobRepository(settings.jobs_dir)
    js = JobService(settings=settings, repository=repo, notebook_service_factory=_Factory(_RaisingDownloadService()), notebook_repository=NotebookRepository(settings.sqlite_db_path), source_builder=SourceBuilderService(), artifact_service=ArtifactService(settings.artifacts_dir))

    now = datetime.now(timezone.utc)
    job = JobRecord(id="job-x", name="j", type=JobType.generate_audio_summary, status=JobStatus.running, input={}, created_at=now, updated_at=now, account_id="acc_a", notebook_id="nb", result={"artifact_reference": "ref"})
    repo.save(job)

    asyncio.run(js._background_download(job, "ref"))

    saved = repo.get("job-x")
    assert saved is not None
    assert saved.status == JobStatus.failed
    assert saved.error  # informacao util presente
    for token in FORBIDDEN:
        assert token not in saved.error, f"job.error vazou: {token}"


# =========================================================================
# Web UI: nao renderiza excecao crua
# =========================================================================

def test_web_route_sanitizes_error(tmp_path: Path) -> None:
    client = _build_client(tmp_path)
    client.app.state.notebook_catalog_service.create_and_persist = AsyncMock(side_effect=Exception(SECRET))
    resp = client.post("/web/notebooks/create", data={"title": "x"})
    assert resp.status_code == 200  # render do card de erro
    for token in FORBIDDEN:
        assert token not in resp.text, f"web vazou: {token}"
