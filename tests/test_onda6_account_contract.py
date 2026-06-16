"""Onda 6 - contrato publico seguro de contas.

TDD: escritos ANTES da implementacao. Sem sessao real do Google.
AccountResponse nao pode mais expor storage_state_path/chrome_profile_path nem
last_error textual; ganha enabled/has_chrome_profile e mantem has_storage_state.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from notebooklm.exceptions import AuthError

from app.core.config import Settings
from app.main import create_app
from app.services.notebooklm_service import MockNotebookLMService

TOKEN = "tkn-onda6"
_FORBIDDEN_PATHS = ["/home/", "/app/", "/tmp/", "data/accounts", "storage_state.json", "chrome-profile", "storage_state_path", "chrome_profile_path"]


def _client(tmp_path: Path, *, token: str | None = None, insecure: bool = True) -> TestClient:
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
        api_auth_token=token,
        allow_insecure_no_auth=insecure,
    )
    return TestClient(create_app(settings), raise_server_exceptions=False)


def _create_account(client: TestClient, alias: str = "sec") -> str:
    resp = client.post("/accounts", json={"alias": alias})
    assert resp.status_code == 201
    return resp.json()["id"]


def _fake_storage() -> dict[str, object]:
    return {"cookies": [{"name": "SID", "value": "x", "domain": ".google.com", "path": "/"}], "origins": []}


# --- Ausencia de paths internos ------------------------------------------

def test_list_accounts_has_no_internal_paths(tmp_path: Path) -> None:
    client = _client(tmp_path)
    body = client.get("/accounts")
    assert body.status_code == 200
    item = body.json()[0]
    assert "storage_state_path" not in item
    assert "chrome_profile_path" not in item
    text = json.dumps(body.json())
    for token in _FORBIDDEN_PATHS:
        assert token not in text, f"vazou: {token}"


def test_get_account_has_no_internal_paths(tmp_path: Path) -> None:
    client = _client(tmp_path)
    acc = _create_account(client)
    resp = client.get(f"/accounts/{acc}")
    assert resp.status_code == 200
    data = resp.json()
    assert "storage_state_path" not in data
    assert "chrome_profile_path" not in data
    for token in _FORBIDDEN_PATHS:
        assert token not in json.dumps(data)


def test_status_route_has_no_internal_paths(tmp_path: Path) -> None:
    client = _client(tmp_path)
    acc = _create_account(client)
    resp = client.get(f"/accounts/{acc}/status")
    assert resp.status_code == 200
    for token in _FORBIDDEN_PATHS:
        assert token not in json.dumps(resp.json())


# --- Campos seguros presentes --------------------------------------------

def test_safe_fields_present(tmp_path: Path) -> None:
    client = _client(tmp_path)
    data = client.get("/accounts").json()[0]
    for field in ["id", "alias", "status", "is_default", "enabled", "has_storage_state", "has_chrome_profile", "created_at", "last_verified_at"]:
        assert field in data, f"faltou campo seguro: {field}"


def test_enabled_true_when_not_disabled(tmp_path: Path) -> None:
    client = _client(tmp_path)
    acc = _create_account(client)  # status inicial 'warming'
    data = client.get(f"/accounts/{acc}").json()
    assert data["status"] != "disabled"
    assert data["enabled"] is True


def test_enabled_false_when_disabled(tmp_path: Path) -> None:
    client = _client(tmp_path)
    acc = _create_account(client)
    assert client.post(f"/accounts/{acc}/disable", json={"detail": None}).status_code == 200
    data = client.get(f"/accounts/{acc}").json()
    assert data["status"] == "disabled"
    assert data["enabled"] is False


def test_has_storage_state_reflects_reality(tmp_path: Path) -> None:
    client = _client(tmp_path)
    acc = _create_account(client)
    assert client.get(f"/accounts/{acc}").json()["has_storage_state"] is False
    saved = client.post("/auth/storage-state", headers={"X-NotebookLM-Account-Id": acc}, json=_fake_storage())
    assert saved.status_code == 200
    assert client.get(f"/accounts/{acc}").json()["has_storage_state"] is True


def test_has_chrome_profile_reflects_reality(tmp_path: Path) -> None:
    client = _client(tmp_path)
    acc = _create_account(client)
    # diretorio chrome-profile e criado na criacao da conta
    assert client.get(f"/accounts/{acc}").json()["has_chrome_profile"] is True
    chrome_dir = client.app.state.account_registry.get_chrome_profile_path(acc)
    shutil.rmtree(chrome_dir)
    assert client.get(f"/accounts/{acc}").json()["has_chrome_profile"] is False


def test_is_default_still_works(tmp_path: Path) -> None:
    client = _client(tmp_path)
    accounts = client.get("/accounts").json()
    default = next(a for a in accounts if a["id"] == "default")
    assert default["is_default"] is True
    acc = _create_account(client)
    assert client.get(f"/accounts/{acc}").json()["is_default"] is False


# --- last_error textual nao deve aparecer --------------------------------

def test_last_error_textual_not_exposed(tmp_path: Path) -> None:
    client = _client(tmp_path)
    acc = _create_account(client)
    secret_detail = "falha em /home/u/data/accounts/acc/storage_state.json cookie SID=zzz"
    assert client.post(f"/accounts/{acc}/disable", json={"detail": secret_detail}).status_code == 200
    data = client.get(f"/accounts/{acc}").json()
    assert "last_error" not in data
    assert secret_detail not in json.dumps(data)
    for token in _FORBIDDEN_PATHS:
        assert token not in json.dumps(data)


# --- Auth da Onda 5 continua valendo -------------------------------------

def test_auth_still_enforced_when_enabled(tmp_path: Path) -> None:
    client = _client(tmp_path, token=TOKEN, insecure=False)
    assert client.get("/accounts").status_code == 401
    assert client.get("/accounts", headers={"Authorization": f"Bearer {TOKEN}"}).status_code == 200


def test_insecure_mode_still_works(tmp_path: Path) -> None:
    assert _client(tmp_path, insecure=True).get("/accounts").status_code == 200


# --- Envelope de erro da Onda 4 continua seguro --------------------------

def test_onda4_error_envelope_still_safe(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(MockNotebookLMService, "verify_access", AsyncMock(side_effect=AuthError("cookie SID=x at /home/u/storage_state.json")))
    client = _client(tmp_path)
    resp = client.post("/notebooks", json={"title": "x"})
    assert resp.status_code == 401
    assert resp.json().get("code") == "AUTH_REQUIRED"
    for token in ["cookie", "SID", "/home/", "storage_state.json"]:
        assert token not in resp.text
