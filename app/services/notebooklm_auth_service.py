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
    StorageCookie,
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

    def is_relevant_domain(self, domain: str) -> bool:
        relevant_domains = {".google.com", "google.com", "notebooklm.google.com", ".notebooklm.google.com"}
        return domain in relevant_domains or any(domain.endswith(d) for d in relevant_domains)

    def is_relevant_cookie(self, name: str) -> bool:
        exact_names = {"SID", "HSID", "SSID", "SAPISID", "APISID", "OSID"}
        if name in exact_names:
            return True
        if name.startswith("__Secure-") and ("PSID" in name or "PAPISID" in name or "OSID" in name):
            return True
        return False

    def has_minimum_cookies(self, names: set[str]) -> bool:
        # Pelo menos um cookie de sessao basico (SID) ou tokens mais modernos (1PSID)
        return "SID" in names or any("1PSID" in n for n in names)

    def filter_payload(self, payload: StorageStatePayload) -> tuple[StorageStatePayload, int, int, list[str], bool]:
        original_count = len(payload.cookies)
        filtered_cookies = []
        kept_names = set()

        for c in payload.cookies:
            if self.is_relevant_domain(c.domain) and self.is_relevant_cookie(c.name):
                filtered_cookies.append(c)
                kept_names.add(c.name)

        payload.cookies = filtered_cookies
        kept_names_list = sorted(list(kept_names))
        has_min = self.has_minimum_cookies(kept_names)

        return payload, original_count, len(filtered_cookies), kept_names_list, has_min

    def save_storage_state(self, payload: StorageStatePayload) -> StorageStateSaveResponse:
        filtered_payload, received, kept, names, has_min = self.filter_payload(payload)
        self._storage_state_service.save(filtered_payload)
        
        detail_msg = f"Storage state filtrado e salvo com {kept} cookies relevantes (de {received} recebidos)."
        if not has_min:
            detail_msg += " ALERTA: Conjunto de cookies parece fraco/incompleto para autenticação."
        else:
            detail_msg += " Conjunto parece suficiente para autenticação."

        return StorageStateSaveResponse(
            storage_state_present=True,
            storage_state_valid=True,
            cookie_count_received=received,
            cookie_count_kept=kept,
            kept_cookie_names=names,
            has_minimum_auth_cookies=has_min,
            notebooklm_access_ok=False,  # Será avaliado em status real
            detail=detail_msg
        )

    async def get_status(self, notebook_service: NotebookLMService) -> AuthStatusResponse:
        if not self._storage_state_service.exists():
            return AuthStatusResponse(
                storage_state_present=False,
                storage_state_valid=False,
                cookie_count=0,
                notebooklm_access_ok=False,
                detail="Storage state ausente. Importe cookies em /auth/storage-state.",
            )

        raw_data = self._storage_state_service.load()
        storage_state_valid = False
        cookie_count = 0
        try:
            if raw_data:
                payload = StorageStatePayload.model_validate(raw_data)
                storage_state_valid = True
                cookie_count = len(payload.cookies)
        except Exception:
            pass

        access = await notebook_service.verify_access()
        detail = access.detail
        if storage_state_valid and not access.ok and "ausente" not in detail.lower():
            detail = f"Storage state salvo ({cookie_count} cookies), mas acesso real ainda nao validado. Erro original: {access.detail}"

        return AuthStatusResponse(
            storage_state_present=True,
            storage_state_valid=storage_state_valid,
            cookie_count=cookie_count,
            notebooklm_access_ok=access.ok,
            detail=detail,
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

        # Re-use filter_payload before saving
        filtered_payload, received, kept, names, has_min = self.filter_payload(payload.storage_state)
        self._storage_state_service.save(filtered_payload)
        self._sessions.pop(payload.session_id, None)
        return LoginCompleteResponse(completed=True, detail="Autenticacao assistida concluida e cookies filtrados.")
