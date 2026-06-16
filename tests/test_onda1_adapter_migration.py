"""Onda 1 - testes de migracao do adapter para notebooklm-py>=0.7.1,<0.8.

Escritos ANTES da implementacao (TDD). Provam, com mocks/fakes e sem nenhuma
sessao real do Google:

1. list_artifacts funciona com objetos que expoem `.kind` (ArtifactType).
2. list_artifacts NAO depende mais de `.artifact_type` (removido na lib >=0.5).
3. verify_access usa from_storage como async context manager, sem `await` direto.
4. UnknownRPCMethodError/RPCError em list_notebooks vira NotebookLMOperationError
   (nao e tratado como "lista vazia").
5. Drift upstream durante o sync NAO apaga o catalogo local.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from notebooklm import ArtifactType
from notebooklm.exceptions import UnknownRPCMethodError

from app.services.notebook_catalog_service import NotebookCatalogService
from app.services.notebook_repository import NotebookRepository
from app.services.notebooklm_service import NotebookLMOperationError, NotebookLMPyService
from app.services.storage_state_service import StorageStateService


# --- Fakes -----------------------------------------------------------------

class _DualModeClientCM:
    """Mimetiza o wrapper de from_storage: e await-able E async context manager.

    Permite que um unico fake atenda tanto a forma antiga
    (``async with await self._get_client()``) quanto a nova
    (``async with self._get_client()``) durante a migracao.
    """

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


class _PureAsyncCM:
    """Async context manager que NAO e await-able (sem __await__).

    Se o codigo tentar ``await from_storage(...)`` (forma deprecada), levanta
    TypeError -- e exatamente o discriminador do teste 3.
    """

    def __init__(self, client: object) -> None:
        self._client = client

    async def __aenter__(self) -> object:
        return self._client

    async def __aexit__(self, *exc: object) -> bool:
        return False


class _FakeArtifact:
    """Artifact no estilo notebooklm-py>=0.5: expoe `.kind`, NAO `.artifact_type`."""

    def __init__(
        self,
        *,
        id: str,
        title: str,
        kind: ArtifactType,
        is_completed: bool,
        created_at: str,
    ) -> None:
        self.id = id
        self.title = title
        self.kind = kind
        self.is_completed = is_completed
        self.created_at = created_at


def _make_service(tmp_path: Path, *, with_storage: bool = True) -> NotebookLMPyService:
    storage_path = tmp_path / "auth" / "storage_state.json"
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    if with_storage:
        storage_path.write_text('{"cookies": [], "origins": []}', encoding="utf-8")
    return NotebookLMPyService(storage_state_service=StorageStateService(storage_path))


# --- Testes 1 & 2: list_artifacts usa .kind, nao .artifact_type ------------

def test_list_artifacts_uses_kind(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    art = _FakeArtifact(
        id="a1",
        title="Episodio",
        kind=ArtifactType.AUDIO,
        is_completed=True,
        created_at="2026-01-01T00:00:00Z",
    )
    fake_client = MagicMock()
    fake_client.artifacts.list = AsyncMock(return_value=[art])
    service._get_client = lambda *a, **k: _DualModeClientCM(fake_client)  # type: ignore[method-assign]

    result = asyncio.run(service.list_artifacts("nb1"))

    assert result == [
        {
            "id": "a1",
            "title": "Episodio",
            "media_type": "audio",
            "is_completed": True,
            "created_at": "2026-01-01T00:00:00Z",
        }
    ]


def test_list_artifacts_does_not_require_artifact_type(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    art = _FakeArtifact(
        id="v1",
        title="Video",
        kind=ArtifactType.VIDEO,
        is_completed=False,
        created_at="",
    )
    # Garante que o objeto nao expoe o atributo antigo (removido na lib).
    assert not hasattr(art, "artifact_type")
    fake_client = MagicMock()
    fake_client.artifacts.list = AsyncMock(return_value=[art])
    service._get_client = lambda *a, **k: _DualModeClientCM(fake_client)  # type: ignore[method-assign]

    result = asyncio.run(service.list_artifacts("nb1"))

    assert result[0]["media_type"] == "video"
    assert set(result[0]) == {"id", "title", "media_type", "is_completed", "created_at"}


# --- Teste 3: from_storage usado como CM, sem await direto ------------------

def test_verify_access_uses_from_storage_without_direct_await(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = _make_service(tmp_path)
    fake_client = MagicMock()
    fake_client.notebooks.list = AsyncMock(return_value=[])

    import notebooklm

    # from_storage SINCRONO retornando um CM que NAO e await-able: se o adapter
    # ainda fizer `await from_storage(...)`, isso levanta TypeError (RED).
    monkeypatch.setattr(
        notebooklm.NotebookLMClient,
        "from_storage",
        lambda *a, **k: _PureAsyncCM(fake_client),
    )

    result = asyncio.run(service.verify_access())

    assert result.ok is True


# --- Teste 4: drift em list_notebooks NAO vira lista vazia -----------------

def test_list_notebooks_drift_raises_domain_error(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    fake_client = MagicMock()
    fake_client.notebooks.list = AsyncMock(side_effect=UnknownRPCMethodError("simulated drift"))
    service._get_client = lambda *a, **k: _DualModeClientCM(fake_client)  # type: ignore[method-assign]

    with pytest.raises(NotebookLMOperationError):
        asyncio.run(service.list_notebooks())


# --- Teste 5: drift no sync NAO apaga catalogo local -----------------------

def test_sync_drift_does_not_wipe_local_catalog(tmp_path: Path) -> None:
    repo = NotebookRepository(tmp_path / "notebooks.db")
    repo.upsert_notebook(
        notebook_id="nb-local-1",
        title="Notebook Local",
        source_count=1,
        artifact_count=0,
        origin="local_created",
        account_id="default",
    )
    assert len(repo.list_all("default")) == 1

    service = _make_service(tmp_path)
    fake_client = MagicMock()
    fake_client.notebooks.list = AsyncMock(side_effect=UnknownRPCMethodError("simulated drift"))
    service._get_client = lambda *a, **k: _DualModeClientCM(fake_client)  # type: ignore[method-assign]

    catalog = NotebookCatalogService(repository=repo, notebook_service=service, account_id="default")

    with pytest.raises(NotebookLMOperationError):
        asyncio.run(catalog.sync_from_account())

    # Catalogo local preservado: drift != "remoto vazio".
    assert len(repo.list_all("default")) == 1
