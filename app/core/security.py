"""Autenticacao Bearer da API (default-deny).

- ALLOW_INSECURE_NO_AUTH=true libera as rotas (apenas dev local explicito).
- Sem API_AUTH_TOKEN configurado e fora do modo inseguro: recusa (401).
- Caso contrario exige `Authorization: Bearer <API_AUTH_TOKEN>`, comparado em
  tempo constante (`secrets.compare_digest`).
- O header Authorization e o token NUNCA sao logados.
"""
from __future__ import annotations

import secrets

from fastapi import Header, HTTPException, Request, status


def _bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer":
        return None
    value = value.strip()
    return value or None


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Autenticacao necessaria.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_auth(
    request: Request,
    authorization: str | None = Header(default=None),
) -> None:
    settings = request.app.state.settings
    if getattr(settings, "allow_insecure_no_auth", False):
        return
    configured = getattr(settings, "api_auth_token", None)
    if not configured:
        # Default-deny: nenhum token configurado e modo nao-inseguro.
        raise _unauthorized()
    presented = _bearer_token(authorization)
    if presented is None or not secrets.compare_digest(presented, configured):
        raise _unauthorized()
