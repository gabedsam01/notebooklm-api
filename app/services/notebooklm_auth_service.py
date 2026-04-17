from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict
from uuid import uuid4

from app.models.auth import (
    AuthStatusResponse,
    LoginCompleteRequest,
    LoginCompleteResponse,
    LoginStartResponse,
    StorageStatePayload,
    StorageStateSaveResponse,
)
from app.services.notebooklm_service import NotebookLMService
from app.services.storage_state_service import StorageStateService


@dataclass(slots=True)
class _LoginSession:
    session_id: str
    expires_at: datetime


class NotebookLMAuthService:
    def __init__(self, storage_state_service: StorageStateService, login_ttl_minutes: int = 20) -> None:
        self._storage_state_service = storage_state_service
        self._login_ttl_minutes = login_ttl_minutes
        self._sessions: Dict[str, _LoginSession] = {}

    def save_storage_state(self, payload: StorageStatePayload) -> StorageStateSaveResponse:
        self._storage_state_service.save(payload)
        return StorageStateSaveResponse(saved=True, detail="Storage state salvo com sucesso.")

    async def get_status(self, notebook_service: NotebookLMService) -> AuthStatusResponse:
        if not self._storage_state_service.exists():
            return AuthStatusResponse(
                storage_state_present=False,
                notebooklm_access_ok=False,
                detail="Storage state ausente. Importe cookies em /auth/storage-state.",
            )

        access = await notebook_service.verify_access()
        return AuthStatusResponse(
            storage_state_present=True,
            notebooklm_access_ok=access.ok,
            detail=access.detail,
        )

    def start_login_flow(self) -> LoginStartResponse:
        now = datetime.now(timezone.utc)
        session_id = uuid4().hex
        expires_at = now + timedelta(minutes=self._login_ttl_minutes)
        self._sessions[session_id] = _LoginSession(session_id=session_id, expires_at=expires_at)

        return LoginStartResponse(
            session_id=session_id,
            expires_at=expires_at,
            detail=(
                "Fluxo assistido iniciado. Faça login manual no Google/NotebookLM em um browser "
                "controlado por voce e envie o storage state em /auth/login/complete."
            ),
        )

    def complete_login_flow(self, payload: LoginCompleteRequest) -> LoginCompleteResponse:
        session = self._sessions.get(payload.session_id)
        if session is None:
            return LoginCompleteResponse(completed=False, detail="Sessao de login nao encontrada.")

        if session.expires_at < datetime.now(timezone.utc):
            self._sessions.pop(payload.session_id, None)
            return LoginCompleteResponse(completed=False, detail="Sessao de login expirada.")

        self._storage_state_service.save(payload.storage_state)
        self._sessions.pop(payload.session_id, None)
        return LoginCompleteResponse(completed=True, detail="Autenticacao assistida concluida.")
