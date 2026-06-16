"""Fixtures compartilhadas + invariantes de isolamento dos testes."""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app

REPO_ROOT = Path(__file__).resolve().parent.parent
TEST_TOKEN = "test-token-onda7"


# --- Defaults / invariantes (autouse) ------------------------------------

@pytest.fixture(autouse=True)
def _tests_default_insecure_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    """Modo dev inseguro por padrao (testes pre-Onda-5 batem sem Bearer).

    Testes de auth da Onda 5+ passam ``allow_insecure_no_auth=False`` explicito,
    que sobrescreve este default via init-args do Settings.
    """
    monkeypatch.setenv("ALLOW_INSECURE_NO_AUTH", "true")


@pytest.fixture(autouse=True)
def _restore_cwd():
    """Isola o cwd: restaura apos cada teste (a CLI faz os.chdir sem restaurar)."""
    cwd = os.getcwd()
    try:
        yield
    finally:
        os.chdir(cwd)


@pytest.fixture(autouse=True)
def _no_notebooklm_home_leak():
    """Guarda de regressao da Onda 2: nenhum teste deve setar NOTEBOOKLM_HOME."""
    before = os.environ.get("NOTEBOOKLM_HOME")
    try:
        yield
    finally:
        after = os.environ.get("NOTEBOOKLM_HOME")
        if before is None:
            os.environ.pop("NOTEBOOKLM_HOME", None)
        else:
            os.environ["NOTEBOOKLM_HOME"] = before
        assert after == before, "um teste alterou NOTEBOOKLM_HOME (regressao da Onda 2)"


# --- Fixtures factory (settings / client / token) ------------------------

@pytest.fixture
def auth_token() -> str:
    return TEST_TOKEN


@pytest.fixture
def make_settings(tmp_path: Path):
    """Factory de Settings temporarias (modo mock; paths sob tmp_path)."""

    def _make(*, subdir: str = "data", **overrides: object) -> Settings:
        data = tmp_path / subdir
        base: dict[str, object] = dict(
            data_dir=data,
            jobs_dir=data / "jobs",
            artifacts_dir=data / "artifacts",
            temp_dir=data / "tmp",
            storage_state_path=data / "auth" / "storage_state.json",
            accounts_dir=data / "accounts",
            sqlite_db_path=data / "notebooks.db",
            templates_dir=REPO_ROOT / "app" / "templates",
            static_dir=REPO_ROOT / "app" / "static",
            notebooklm_mode="mock",
            worker_poll_interval_seconds=0.01,
        )
        base.update(overrides)
        return Settings(**base)

    return _make


@pytest.fixture
def make_client(make_settings):
    """Factory de TestClient (raise_server_exceptions=False)."""

    def _make(**overrides: object) -> TestClient:
        return TestClient(create_app(make_settings(**overrides)), raise_server_exceptions=False)

    return _make


@pytest.fixture
def insecure_client(make_client) -> TestClient:
    """Client em modo dev inseguro (sem Bearer)."""
    return make_client(allow_insecure_no_auth=True)


@pytest.fixture
def authed_client(make_client) -> TestClient:
    """Client com auth Bearer ativa (use ``Authorization: Bearer <auth_token>``)."""
    return make_client(api_auth_token=TEST_TOKEN, allow_insecure_no_auth=False)
