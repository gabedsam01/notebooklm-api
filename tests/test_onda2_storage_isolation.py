"""Onda 2 - storage por conta + remocao de NOTEBOOKLM_HOME global e global_env_lock.

TDD: escritos ANTES da implementacao. Sem sessao real do Google, sem cookies
reais. Patcham notebooklm.NotebookLMClient.from_storage por um gravador que
registra o path usado e o valor de os.environ['NOTEBOOKLM_HOME'] no momento do
download.

RED esperados (codigo atual): testes 1, 4, 6, 7, 8.
Guards (ja verdes; travam o isolamento por path que substitui o env): 2, 3, 5, 9.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import notebooklm

from app.core.config import Settings
from app.services.account_registry_service import AccountRegistryService
from app.services.notebooklm_factory import NotebookLMServiceFactory
from app.services.notebooklm_service import NotebookLMPyService
from app.services.storage_state_service import StorageStateService


# --- Helpers ---------------------------------------------------------------

class _PureAsyncCM:
    """Async context manager simples (nao await-able)."""

    def __init__(self, client: object) -> None:
        self._client = client

    async def __aenter__(self) -> object:
        return self._client

    async def __aexit__(self, *exc: object) -> bool:
        return False


def _make_service(tmp_path: Path, name: str) -> NotebookLMPyService:
    storage_path = tmp_path / name / "storage_state.json"
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_text('{"cookies": [], "origins": []}', encoding="utf-8")
    return NotebookLMPyService(storage_state_service=StorageStateService(storage_path))


def _make_settings(tmp_path: Path, mode: str = "mock") -> Settings:
    data = tmp_path / "data"
    return Settings(
        data_dir=data,
        jobs_dir=data / "jobs",
        artifacts_dir=data / "artifacts",
        temp_dir=data / "tmp",
        storage_state_path=data / "auth" / "storage_state.json",
        accounts_dir=data / "accounts",
        sqlite_db_path=data / "notebooks.db",
        notebooklm_mode=mode,
    )


def _patch_from_storage(monkeypatch, recorded_paths: list[str], recorded_home: list[str | None]) -> None:
    """from_storage gravador: registra path e o NOTEBOOKLM_HOME visto no download."""

    def _fs(path, *args, **kwargs):  # type: ignore[no-untyped-def]
        recorded_paths.append(str(path))
        client = MagicMock()

        async def _download(*, notebook_id, output_path, artifact_id, **kw):  # type: ignore[no-untyped-def]
            recorded_home.append(os.environ.get("NOTEBOOKLM_HOME"))
            out = Path(output_path)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(b"artifact-bytes")

        client.artifacts.download_audio = AsyncMock(side_effect=_download)
        client.artifacts.download_video = AsyncMock(side_effect=_download)
        return _PureAsyncCM(client)

    monkeypatch.setattr(notebooklm.NotebookLMClient, "from_storage", _fs)


# --- Teste 1: download nao altera os.environ['NOTEBOOKLM_HOME'] -------------

def test_download_does_not_mutate_notebooklm_home(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("NOTEBOOKLM_HOME", raising=False)
    paths: list[str] = []
    homes: list[str | None] = []
    _patch_from_storage(monkeypatch, paths, homes)
    service = _make_service(tmp_path, "acc_a")

    dest = tmp_path / "out" / "a.wav"
    asyncio.run(service.download_artifact("nb1", "art1", dest, media_type="audio"))

    assert homes == [None]  # nada de NOTEBOOKLM_HOME setado durante o download
    assert "NOTEBOOKLM_HOME" not in os.environ  # nem depois
    assert dest.exists()


# --- Teste 2: download usa o storage_state da conta correta ----------------

def test_download_uses_account_storage_state(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("NOTEBOOKLM_HOME", raising=False)
    paths: list[str] = []
    homes: list[str | None] = []
    _patch_from_storage(monkeypatch, paths, homes)
    service = _make_service(tmp_path, "acc_a")
    expected = str(tmp_path / "acc_a" / "storage_state.json")

    asyncio.run(service.download_artifact("nb1", "art1", tmp_path / "out" / "a.wav", media_type="audio"))

    assert paths == [expected]


# --- Teste 3: contas diferentes -> storage_state_path diferentes -----------

def test_two_accounts_have_distinct_storage_paths(tmp_path: Path) -> None:
    registry = AccountRegistryService(_make_settings(tmp_path))
    registry.ensure_default_account()
    other = registry.create_account(alias="b")

    assert registry.get_storage_state_path("default") != registry.get_storage_state_path(other.id)


# --- Teste 4: downloads concorrentes nao dependem de NOTEBOOKLM_HOME --------

def test_concurrent_downloads_do_not_depend_on_notebooklm_home(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("NOTEBOOKLM_HOME", raising=False)
    paths: list[str] = []
    homes: list[str | None] = []
    _patch_from_storage(monkeypatch, paths, homes)
    svc_a = _make_service(tmp_path, "acc_a")
    svc_b = _make_service(tmp_path, "acc_b")

    async def run() -> None:
        await asyncio.gather(
            svc_a.download_artifact("nb_a", "art_a", tmp_path / "out" / "a.wav", media_type="audio"),
            svc_b.download_artifact("nb_b", "art_b", tmp_path / "out" / "b.wav", media_type="audio"),
        )

    asyncio.run(run())

    assert homes == [None, None]  # nenhum download dependeu de/alterou o env global
    assert "NOTEBOOKLM_HOME" not in os.environ


# --- Teste 5: downloads concorrentes usam o path correto de cada conta ------

def test_concurrent_downloads_use_correct_per_account_paths(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("NOTEBOOKLM_HOME", raising=False)
    paths: list[str] = []
    homes: list[str | None] = []
    _patch_from_storage(monkeypatch, paths, homes)
    svc_a = _make_service(tmp_path, "acc_a")
    svc_b = _make_service(tmp_path, "acc_b")

    async def run() -> None:
        await asyncio.gather(
            svc_a.download_artifact("nb_a", "art_a", tmp_path / "out" / "a.wav", media_type="audio"),
            svc_b.download_artifact("nb_b", "art_b", tmp_path / "out" / "b.wav", media_type="audio"),
        )

    asyncio.run(run())

    assert set(paths) == {
        str(tmp_path / "acc_a" / "storage_state.json"),
        str(tmp_path / "acc_b" / "storage_state.json"),
    }


# --- Teste 6: startup do app nao seta NOTEBOOKLM_HOME global ----------------

def test_create_app_does_not_set_notebooklm_home(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("NOTEBOOKLM_HOME", raising=False)
    from app.main import create_app

    create_app(_make_settings(tmp_path))

    assert "NOTEBOOKLM_HOME" not in os.environ


# --- Teste 7: sem global_env_lock no modulo do adapter ---------------------

def test_no_global_env_lock_in_adapter_module() -> None:
    import app.services.notebooklm_service as adapter_module

    assert not hasattr(adapter_module, "global_env_lock")


# --- Teste 8: sem _sync_notebooklm_home em main ----------------------------

def test_no_sync_notebooklm_home_in_main() -> None:
    import app.main as main_module

    assert not hasattr(main_module, "_sync_notebooklm_home")


# --- Teste 9: wrapper cacheado, mas NotebookLMClient nao compartilhado ------

def test_factory_caches_wrapper_not_client(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path, mode="real")  # real -> wrapper NotebookLMPyService
    registry = AccountRegistryService(settings)
    registry.ensure_default_account()
    other = registry.create_account(alias="b")
    factory = NotebookLMServiceFactory(settings=settings, registry=registry)

    default_1 = factory.get_service("default")
    default_2 = factory.get_service("default")
    other_svc = factory.get_service(other.id)

    assert default_1 is default_2  # wrapper cacheado por conta
    assert default_1 is not other_svc  # contas diferentes -> wrappers diferentes
    assert (
        default_1._storage_state_service.storage_state_path
        != other_svc._storage_state_service.storage_state_path
    )
    # Nenhum NotebookLMClient real fica preso no wrapper (e criado por operacao).
    assert not hasattr(default_1, "_client")
