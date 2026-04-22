from __future__ import annotations

from app.core.config import Settings
from app.services.account_registry_service import AccountRegistryService
from app.services.notebooklm_service import MockNotebookLMService, NotebookLMPyService, NotebookLMService
from app.services.storage_state_service import StorageStateService


class NotebookLMServiceFactory:
    def __init__(self, settings: Settings, registry: AccountRegistryService) -> None:
        self._settings = settings
        self._registry = registry
        self._cache: dict[str, NotebookLMService] = {}

    def get_service(self, account_id: str) -> NotebookLMService:
        if account_id in self._cache:
            return self._cache[account_id]
        storage = StorageStateService(self._registry.get_storage_state_path(account_id))
        if self._settings.notebooklm_mode == 'real':
            service: NotebookLMService = NotebookLMPyService(storage_state_service=storage)
        else:
            service = MockNotebookLMService(storage_state_service=storage)
        self._cache[account_id] = service
        return service
