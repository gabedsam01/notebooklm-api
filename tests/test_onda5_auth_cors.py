"""Onda 5 - autenticacao Bearer (default-deny) + CORS configuravel.

TDD: escritos ANTES da implementacao. Sem sessao real do Google.
Cada cliente constroi Settings explicitas (api_auth_token/allow_insecure_no_auth/
cors_*), entao independem do conftest.
"""
from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from notebooklm.exceptions import AuthError

from app.core.config import Settings
from app.main import create_app
from app.services.notebooklm_service import MockNotebookLMService

TOKEN = "secret-tkn-xyz-123"


def _client(
    tmp_path: Path,
    *,
    token: str | None = TOKEN,
    insecure: bool = False,
    cors_origins: str = "",
    cors_credentials: bool = False,
) -> TestClient:
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
        cors_allow_origins=cors_origins,
        cors_allow_credentials=cors_credentials,
    )
    return TestClient(create_app(settings), raise_server_exceptions=False)


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# =========================================================================
# Autenticacao
# =========================================================================

def test_health_public_without_token(tmp_path: Path) -> None:
    assert _client(tmp_path).get("/health").status_code == 200


def test_sensitive_without_token_is_401(tmp_path: Path) -> None:
    assert _client(tmp_path).get("/accounts").status_code == 401


def test_sensitive_with_wrong_token_is_401(tmp_path: Path) -> None:
    assert _client(tmp_path).get("/accounts", headers=_bearer("WRONG-SECRET")).status_code == 401


def test_authorization_without_bearer_is_401(tmp_path: Path) -> None:
    # header sem o esquema "Bearer "
    assert _client(tmp_path).get("/accounts", headers={"Authorization": TOKEN}).status_code == 401


def test_correct_bearer_works(tmp_path: Path) -> None:
    assert _client(tmp_path).get("/accounts", headers=_bearer(TOKEN)).status_code == 200


def test_uses_compare_digest(tmp_path: Path, monkeypatch) -> None:
    import app.core.security as sec

    calls: list[tuple] = []
    real = sec.secrets.compare_digest

    def spy(a, b):  # type: ignore[no-untyped-def]
        calls.append((a, b))
        return real(a, b)

    monkeypatch.setattr(sec.secrets, "compare_digest", spy)
    _client(tmp_path).get("/accounts", headers=_bearer(TOKEN))
    assert calls, "comparacao de token deve usar secrets.compare_digest"


def test_default_deny_when_no_token_configured(tmp_path: Path) -> None:
    # sem token e sem modo inseguro -> recusa (nao abre silenciosamente)
    assert _client(tmp_path, token=None, insecure=False).get("/accounts").status_code == 401


def test_insecure_mode_allows_without_token(tmp_path: Path) -> None:
    assert _client(tmp_path, token=None, insecure=True).get("/accounts").status_code == 200


def test_envelope_still_works_with_auth(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(MockNotebookLMService, "verify_access", AsyncMock(side_effect=AuthError("cookie SID=x")))
    resp = _client(tmp_path).post("/notebooks", json={"title": "x"}, headers=_bearer(TOKEN))
    assert resp.status_code == 401
    assert resp.json().get("code") == "AUTH_REQUIRED"  # envelope da Onda 4 (lib AuthError)


def test_request_validation_not_engulfed(tmp_path: Path) -> None:
    resp = _client(tmp_path).post("/notebooks", json={}, headers=_bearer(TOKEN))  # falta title
    assert resp.status_code == 422


# =========================================================================
# CORS
# =========================================================================

def test_cors_closed_by_default(tmp_path: Path) -> None:
    resp = _client(tmp_path, cors_origins="").get("/health", headers={"Origin": "http://evil.com"})
    assert "access-control-allow-origin" not in {k.lower() for k in resp.headers}


def test_cors_allows_configured_origin(tmp_path: Path) -> None:
    resp = _client(tmp_path, cors_origins="http://good.com").get("/health", headers={"Origin": "http://good.com"})
    assert resp.headers.get("access-control-allow-origin") == "http://good.com"


def test_cors_preflight_for_allowed_origin(tmp_path: Path) -> None:
    resp = _client(tmp_path, cors_origins="http://good.com").options(
        "/accounts",
        headers={"Origin": "http://good.com", "Access-Control-Request-Method": "GET"},
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://good.com"


def test_cors_disallowed_origin(tmp_path: Path) -> None:
    resp = _client(tmp_path, cors_origins="http://good.com").get("/health", headers={"Origin": "http://evil.com"})
    assert resp.headers.get("access-control-allow-origin") != "http://evil.com"


def test_cors_credentials_only_with_explicit_origin(tmp_path: Path) -> None:
    r1 = _client(tmp_path / "a", cors_origins="http://good.com", cors_credentials=True).get(
        "/health", headers={"Origin": "http://good.com"}
    )
    assert r1.headers.get("access-control-allow-credentials") == "true"
    # wildcard + credentials -> NUNCA true
    r2 = _client(tmp_path / "b", cors_origins="*", cors_credentials=True).get(
        "/health", headers={"Origin": "http://anything.com"}
    )
    assert r2.headers.get("access-control-allow-credentials") != "true"


def test_cors_allows_authorization_header(tmp_path: Path) -> None:
    resp = _client(tmp_path, cors_origins="http://good.com").options(
        "/accounts",
        headers={
            "Origin": "http://good.com",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert "authorization" in resp.headers.get("access-control-allow-headers", "").lower()


# =========================================================================
# Logs / sanitizacao
# =========================================================================

def test_authorization_not_in_logs(tmp_path: Path, caplog) -> None:
    client = _client(tmp_path)
    with caplog.at_level(logging.DEBUG):
        client.get("/accounts", headers=_bearer(TOKEN))
        client.get("/accounts", headers=_bearer("WRONG-SECRET-LOG"))
    assert TOKEN not in caplog.text
    assert "WRONG-SECRET-LOG" not in caplog.text


def test_wrong_token_not_in_error_response(tmp_path: Path) -> None:
    resp = _client(tmp_path).get("/accounts", headers=_bearer("DO-NOT-LEAK-ME"))
    assert resp.status_code == 401
    assert "DO-NOT-LEAK-ME" not in resp.text


def test_401_is_safe_and_clean(tmp_path: Path) -> None:
    resp = _client(tmp_path).get("/accounts")
    assert resp.status_code == 401
    for token in ["storage_state", "cookie", "chrome-profile", "/home/", "/app/", "/tmp/", "traceback", TOKEN]:
        assert token not in resp.text


# =========================================================================
# Escopo
# =========================================================================

_SENSITIVE = [
    ("get", "/accounts", None),
    ("get", "/auth/status", None),
    ("get", "/notebooks", None),
    ("get", "/jobs", None),
    ("get", "/artifacts/some-id", None),
    ("post", "/sources/text", {"notebook_id": "nb", "title": "t", "content": "c"}),
    ("post", "/operations/audio-summary", {"notebook_id": "nb"}),
]


@pytest.mark.parametrize("method,path,body", _SENSITIVE)
def test_sensitive_routes_protected(tmp_path: Path, method: str, path: str, body) -> None:
    client = _client(tmp_path)
    resp = getattr(client, method)(path, json=body) if body is not None else getattr(client, method)(path)
    assert resp.status_code == 401


def test_web_ui_protected_when_auth_enabled(tmp_path: Path) -> None:
    # Decisao explicita: Web UI fica atras da mesma camada Bearer (sem login proprio).
    assert _client(tmp_path).get("/").status_code == 401


def test_web_ui_open_in_insecure_mode(tmp_path: Path) -> None:
    assert _client(tmp_path, token=None, insecure=True).get("/").status_code == 200
