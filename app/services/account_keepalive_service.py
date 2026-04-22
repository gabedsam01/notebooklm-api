
from __future__ import annotations

import asyncio
import logging

from app.core.config import Settings
from app.services.account_registry_service import AccountRegistryService
from app.services.notebooklm_factory import NotebookLMServiceFactory

logger = logging.getLogger(__name__)


class AccountKeepaliveService:
    def __init__(self, settings: Settings, registry: AccountRegistryService, service_factory: NotebookLMServiceFactory) -> None:
        self._settings = settings
        self._registry = registry
        self._service_factory = service_factory
        self._task: asyncio.Task[None] | None = None
        self._running = False

    async def start(self) -> None:
        if self._settings.account_keepalive_interval_seconds <= 0 or self._task is not None:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop(), name='account-keepalive')

    async def shutdown(self) -> None:
        self._running = False
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def verify_account(self, account_id: str) -> None:
        account = self._registry.get_account(account_id)
        if account is None or account.status == 'disabled':
            return
        service = self._service_factory.get_service(account_id)
        access = await service.verify_access()
        if access.ok:
            self._registry.touch_verified(account_id, None, healthy=True)
        else:
            lowered = access.detail.lower()
            status = 'challenge_required' if any(token in lowered for token in ('challenge', '2fa', 'captcha')) else 'expired'
            self._registry.update_status(account_id, status, access.detail)

    async def _loop(self) -> None:
        while self._running:
            try:
                for account in self._registry.list_accounts():
                    if account.status == 'disabled':
                        continue
                    await self.verify_account(account.id)
            except Exception as exc:  # noqa: BLE001
                logger.warning('Falha no keepalive de contas: %s', exc)
            await asyncio.sleep(self._settings.account_keepalive_interval_seconds)
