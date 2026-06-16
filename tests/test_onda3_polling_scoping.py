"""Onda 3 - terminalidade de polling + scoping de jobs/artefatos por conta.

TDD: escritos ANTES da implementacao. Sem sessao real do Google.

Polling (unit no adapter): completed/failed/removed/not_found(breve/persistente)/
timeout/callback.
Scoping (via TestClient, modo mock): cross-conta deve dar 404, indistinguivel de
"nao existe".
Download/artefato: usa account_id do job, artefato fica preso ao job, path dentro
de artifacts_dir, fallback respeita service(account)/notebook_id.
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.artifact_service import ArtifactService
from app.services.job_repository import LocalJsonJobRepository
from app.services.job_service import JobService
from app.services.notebook_repository import NotebookRepository
from app.services.notebooklm_service import NotebookLMOperationError, NotebookLMPyService
from app.services.source_builder_service import SourceBuilderService
from app.services.storage_state_service import StorageStateService
from app.models.jobs import JobRecord, JobStatus, JobType


# =========================================================================
# Helpers de polling
# =========================================================================

class _DualModeClientCM:
    def __init__(self, client: object) -> None:
        self._client = client

    def __await__(self):  # type: ignore[no-untyped-def]
        async def _identity() -> "_DualModeClientCM":
            return self

        return _identity().__await__()

    async def __aenter__(self) -> object:
        return self._client

    async def __aexit__(self, *exc: object) -> bool:
        return False


def _gs(status: str, task_id: str = "art1", error: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(status=status, task_id=task_id, error=error)


def _poller_service(tmp_path: Path, poll_returns) -> tuple[NotebookLMPyService, MagicMock]:
    storage = tmp_path / "acc" / "storage_state.json"
    storage.parent.mkdir(parents=True, exist_ok=True)
    storage.write_text('{"cookies": [], "origins": []}', encoding="utf-8")
    service = NotebookLMPyService(storage_state_service=StorageStateService(storage))
    fake_client = MagicMock()
    fake_client.artifacts.poll_status = AsyncMock(side_effect=poll_returns)
    service._get_client = lambda *a, **k: _DualModeClientCM(fake_client)  # type: ignore[method-assign]
    return service, fake_client


# --- Polling: completed --------------------------------------------------

def test_poll_completed_returns_reference(tmp_path: Path) -> None:
    service, _ = _poller_service(tmp_path, [_gs("completed", task_id="art1")])
    result = asyncio.run(
        service.wait_for_artifact("nb", "art1", timeout_seconds=5, poll_interval_seconds=0.0)
    )
    assert result == "art1"


# --- Polling: failed -----------------------------------------------------

def test_poll_failed_raises_clean(tmp_path: Path) -> None:
    service, _ = _poller_service(tmp_path, [_gs("failed", error="boom")])
    with pytest.raises(NotebookLMOperationError):
        asyncio.run(service.wait_for_artifact("nb", "art1", timeout_seconds=5, poll_interval_seconds=0.0))


# --- Polling: removed e terminal, sem esperar timeout --------------------

def test_poll_removed_is_terminal_without_timeout(tmp_path: Path) -> None:
    service, fake = _poller_service(tmp_path, lambda **k: _gs("removed", error="quota"))
    with pytest.raises(NotebookLMOperationError):
        asyncio.run(service.wait_for_artifact("nb", "art1", timeout_seconds=1.0, poll_interval_seconds=0.01))
    assert fake.artifacts.poll_status.call_count == 1  # terminal na 1a verificacao


# --- Polling: not_found breve pode continuar -----------------------------

def test_poll_not_found_brief_then_completed(tmp_path: Path) -> None:
    service, _ = _poller_service(
        tmp_path,
        [_gs("not_found"), _gs("not_found"), _gs("completed", task_id="art1")],
    )
    result = asyncio.run(
        service.wait_for_artifact("nb", "art1", timeout_seconds=5, poll_interval_seconds=0.0)
    )
    assert result == "art1"


# --- Polling: not_found persistente falha (politica clara) ---------------

def test_poll_not_found_persistent_fails(tmp_path: Path) -> None:
    service, fake = _poller_service(tmp_path, lambda **k: _gs("not_found"))
    with pytest.raises(NotebookLMOperationError):
        asyncio.run(service.wait_for_artifact("nb", "art1", timeout_seconds=1.0, poll_interval_seconds=0.01))
    # Falha pela politica de not_found persistente (poucas verificacoes), nao por timeout.
    assert fake.artifacts.poll_status.call_count <= 8


# --- Polling: timeout ----------------------------------------------------

def test_poll_timeout_raises_timeouterror(tmp_path: Path) -> None:
    service, _ = _poller_service(tmp_path, lambda **k: _gs("in_progress"))
    with pytest.raises(TimeoutError):
        asyncio.run(service.wait_for_artifact("nb", "art1", timeout_seconds=0.1, poll_interval_seconds=0.01))


# --- Polling: status_callback recebe atualizacoes ------------------------

def test_poll_status_callback_receives_updates(tmp_path: Path) -> None:
    service, _ = _poller_service(
        tmp_path,
        [_gs("pending"), _gs("in_progress"), _gs("completed", task_id="art1")],
    )
    seen: list[str] = []
    result = asyncio.run(
        service.wait_for_artifact(
            "nb", "art1", timeout_seconds=5, poll_interval_seconds=0.0, status_callback=seen.append
        )
    )
    assert result == "art1"
    assert seen == ["pending", "in_progress", "completed"]


# =========================================================================
# Helpers de scoping (TestClient, modo mock)
# =========================================================================

def _build_client(tmp_path: Path) -> TestClient:
    data = tmp_path / "data"
    settings = Settings(
        data_dir=data,
        jobs_dir=data / "jobs",
        artifacts_dir=data / "artifacts",
        temp_dir=data / "tmp",
        storage_state_path=data / "auth" / "storage_state.json",
        accounts_dir=data / "accounts",
        sqlite_db_path=data / "notebooks.db",
        notebooklm_mode="mock",
        worker_poll_interval_seconds=0.01,
    )
    return TestClient(create_app(settings))


def _fake_storage() -> dict[str, object]:
    return {"cookies": [{"name": "SID", "value": "x", "domain": ".google.com", "path": "/"}], "origins": []}


def _headers(account_id: str | None):
    return {"X-NotebookLM-Account-Id": account_id} if account_id else None


def _completed_audio_job(client: TestClient, account_id: str | None = None) -> str:
    h = _headers(account_id)
    assert client.post("/auth/storage-state", headers=h, json=_fake_storage()).status_code == 200
    nb = client.post("/notebooks", headers=h, json={"title": "NB"})
    assert nb.status_code == 201
    notebook_id = nb.json()["notebook_id"]
    assert client.post(
        "/sources/text", headers=h, json={"notebook_id": notebook_id, "title": "S", "content": "C"}
    ).status_code == 200
    created = client.post(
        "/operations/audio-summary?async=true", headers=h, json={"notebook_id": notebook_id}
    )
    assert created.status_code == 202
    job_id = created.json()["id"]
    deadline = time.time() + 6.0
    while time.time() < deadline:
        r = client.get(f"/jobs/{job_id}", headers=h)
        assert r.status_code == 200
        if r.json()["status"] in {"completed", "failed"}:
            break
        time.sleep(0.05)
    return job_id


# --- Scoping: dono acessa --------------------------------------------------

def test_job_accessible_by_owner_account(tmp_path: Path) -> None:
    client = _build_client(tmp_path)
    acc = client.post("/accounts", json={"alias": "b"}).json()["id"]
    job_id = _completed_audio_job(client, account_id=acc)
    assert client.get(f"/jobs/{job_id}", headers=_headers(acc)).status_code == 200


# --- Scoping: conta B nao acessa job da conta A (404) ----------------------

def test_job_not_accessible_cross_account(tmp_path: Path) -> None:
    client = _build_client(tmp_path)
    other = client.post("/accounts", json={"alias": "b"}).json()["id"]
    job_id = _completed_audio_job(client)  # conta default
    assert client.get(f"/jobs/{job_id}", headers=_headers(other)).status_code == 404


# --- Scoping: artefato cross-conta (404) -----------------------------------

def test_artifact_not_accessible_cross_account(tmp_path: Path) -> None:
    client = _build_client(tmp_path)
    other = client.post("/accounts", json={"alias": "b"}).json()["id"]
    job_id = _completed_audio_job(client)  # default
    assert client.get(f"/artifacts/{job_id}").status_code == 200  # dono
    assert client.get(f"/artifacts/{job_id}", headers=_headers(other)).status_code == 404  # cross


# --- Scoping: sem header usa default ---------------------------------------

def test_no_header_uses_default_scoping(tmp_path: Path) -> None:
    client = _build_client(tmp_path)
    other = client.post("/accounts", json={"alias": "b"}).json()["id"]
    job_id = _completed_audio_job(client)  # default
    assert client.get(f"/jobs/{job_id}").status_code == 200
    assert client.get(f"/jobs/{job_id}", headers=_headers(other)).status_code == 404


# --- Scoping: inexistente 404 ----------------------------------------------

def test_nonexistent_job_returns_404(tmp_path: Path) -> None:
    client = _build_client(tmp_path)
    assert client.get("/jobs/does-not-exist").status_code == 404
    assert client.get("/artifacts/does-not-exist").status_code == 404


# --- Scoping: cross-conta indistinguivel de inexistente --------------------

def test_cross_account_indistinguishable_from_missing(tmp_path: Path) -> None:
    client = _build_client(tmp_path)
    other = client.post("/accounts", json={"alias": "b"}).json()["id"]
    job_id = _completed_audio_job(client)  # default
    cross = client.get(f"/jobs/{job_id}", headers=_headers(other))
    missing = client.get("/jobs/does-not-exist", headers=_headers(other))
    assert cross.status_code == missing.status_code == 404
    assert cross.json() == missing.json()  # mesma resposta -> nao revela existencia


# =========================================================================
# Download / artefato (unit em JobService)
# =========================================================================

def _make_settings(tmp_path: Path) -> Settings:
    data = tmp_path / "data"
    return Settings(
        data_dir=data,
        jobs_dir=data / "jobs",
        artifacts_dir=data / "artifacts",
        temp_dir=data / "tmp",
        storage_state_path=data / "auth" / "storage_state.json",
        accounts_dir=data / "accounts",
        sqlite_db_path=data / "notebooks.db",
        notebooklm_mode="mock",
    )


class _SpyFactory:
    def __init__(self, service: object) -> None:
        self._service = service
        self.calls: list[str] = []

    def get_service(self, account_id: str) -> object:
        self.calls.append(account_id)
        return self._service


class _FakeDownloadService:
    def __init__(self) -> None:
        self.list_calls: list[str] = []

    async def list_artifacts(self, notebook_id: str) -> list[dict[str, object]]:
        self.list_calls.append(notebook_id)
        return []

    async def download_artifact(self, *, notebook_id, artifact_reference, destination_path, media_type):  # type: ignore[no-untyped-def]
        Path(destination_path).parent.mkdir(parents=True, exist_ok=True)
        Path(destination_path).write_bytes(b"artifact-bytes")
        return Path(destination_path)


def _build_job_service(tmp_path: Path, factory: object) -> tuple[JobService, LocalJsonJobRepository, Settings]:
    settings = _make_settings(tmp_path)
    repo = LocalJsonJobRepository(settings.jobs_dir)
    js = JobService(
        settings=settings,
        repository=repo,
        notebook_service_factory=factory,  # type: ignore[arg-type]
        notebook_repository=NotebookRepository(settings.sqlite_db_path),
        source_builder=SourceBuilderService(),
        artifact_service=ArtifactService(settings.artifacts_dir),
    )
    return js, repo, settings


def _audio_job(account_id: str, notebook_id: str = "nb") -> JobRecord:
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    return JobRecord(
        id="job-x",
        name="j",
        type=JobType.generate_audio_summary,
        status=JobStatus.running,
        input={},
        created_at=now,
        updated_at=now,
        account_id=account_id,
        notebook_id=notebook_id,
        result={"artifact_reference": "ref-1"},
    )


# --- Download usa o account_id do job + artefato preso ao job_id ----------

def test_background_download_uses_job_account_and_binds_artifact(tmp_path: Path) -> None:
    fake_service = _FakeDownloadService()
    factory = _SpyFactory(fake_service)
    js, repo, _ = _build_job_service(tmp_path, factory)
    job = _audio_job(account_id="acc_a")
    repo.save(job)

    asyncio.run(js._background_download(job, "ref-1"))

    assert factory.calls == ["acc_a"]  # usou o account_id do job
    saved = repo.get("job-x")
    assert saved is not None
    assert saved.status == JobStatus.completed
    assert saved.artifact_path  # artefato associado ao job_id
    assert fake_service.list_calls == ["nb"]  # title lookup no notebook do job


# --- Path do artefato deve ficar dentro de artifacts_dir -----------------

def test_resolve_artifact_path_within_artifacts_dir(tmp_path: Path) -> None:
    js, _, settings = _build_job_service(tmp_path, _SpyFactory(_FakeDownloadService()))
    artifacts_dir = settings.artifacts_dir.resolve()

    # artefato legitimo (relativo a data_dir)
    (artifacts_dir / "ok.wav").parent.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "ok.wav").write_bytes(b"x")
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    ok_job = JobRecord(id="j1", name="j", type=JobType.generate_audio_summary, status=JobStatus.completed, input={}, created_at=now, updated_at=now, account_id="a", artifact_path="artifacts/ok.wav")
    resolved = js.resolve_artifact_path(ok_job)
    assert resolved is not None and resolved.resolve().is_relative_to(artifacts_dir)

    # artefato malicioso (path traversal) -> nao resolve
    bad_job = JobRecord(id="j2", name="j", type=JobType.generate_audio_summary, status=JobStatus.completed, input={}, created_at=now, updated_at=now, account_id="a", artifact_path="../../etc/passwd")
    assert js.resolve_artifact_path(bad_job) is None


# --- Fallback respeita service(account) e notebook_id --------------------

def test_fallback_respects_service_and_notebook(tmp_path: Path) -> None:
    js = JobService.__new__(JobService)
    svc = MagicMock()
    svc.list_artifacts = AsyncMock(
        return_value=[
            {"id": "a0", "is_completed": True, "media_type": "audio", "created_at": "2026-01-01"},
            {"id": "a1", "is_completed": True, "media_type": "audio", "created_at": "2026-01-02"},
            {"id": "v9", "is_completed": True, "media_type": "video", "created_at": "2026-01-03"},
        ]
    )
    found = asyncio.run(js._find_ready_artifact_fallback(svc, "nb-77", "audio"))
    assert found == "a1"  # mais recente do tipo audio
    svc.list_artifacts.assert_awaited_once_with("nb-77")
