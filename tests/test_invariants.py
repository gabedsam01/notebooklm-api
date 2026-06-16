"""Onda 7 - invariantes globais de isolamento + smoke das fixtures consolidadas.

Estes testes nao introduzem comportamento novo: travam invariantes
(cwd estavel, NOTEBOOKLM_HOME nao vazado) e exercitam as fixtures factory
(insecure_client/authed_client/auth_token) para que nao fiquem ociosas.
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi.testclient import TestClient

_REPO_ROOT = str(Path(__file__).resolve().parent.parent)


def test_cwd_is_repo_root_at_test_start() -> None:
    # Invariante: cada teste comeca no repo root. A fixture autouse _restore_cwd
    # isola o os.chdir feito pela CLI (test_cli) em outros testes.
    assert os.getcwd() == _REPO_ROOT


def test_notebooklm_home_not_set_by_tests() -> None:
    # Invariante da Onda 2: nenhum estado global de auth no ambiente.
    assert "NOTEBOOKLM_HOME" not in os.environ


def test_insecure_client_health_is_public(insecure_client: TestClient) -> None:
    assert insecure_client.get("/health").status_code == 200


def test_insecure_client_opens_sensitive_routes(insecure_client: TestClient) -> None:
    assert insecure_client.get("/accounts").status_code == 200


def test_authed_client_requires_bearer(authed_client: TestClient, auth_token: str) -> None:
    assert authed_client.get("/accounts").status_code == 401
    ok = authed_client.get("/accounts", headers={"Authorization": f"Bearer {auth_token}"})
    assert ok.status_code == 200
