"""Fixtures compartilhadas dos testes."""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _tests_default_insecure_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    """Por padrao os testes rodam em modo dev inseguro (sem Bearer).

    Os testes pre-Onda-5 batem em rotas sensiveis sem token. Os testes de auth
    da Onda 5 constroem Settings com ``allow_insecure_no_auth=False`` (e
    ``api_auth_token``) explicitos, que sobrescrevem este default via init-args.
    """
    monkeypatch.setenv("ALLOW_INSECURE_NO_AUTH", "true")
