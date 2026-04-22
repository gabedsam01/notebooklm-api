
from __future__ import annotations

import uuid
from pathlib import Path

from app.core.config import Settings
from app.models.account import AccountMeta, AccountResponse, AccountStatus


class AccountRegistryService:
    DEFAULT_ACCOUNT_ID = "default"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._accounts_dir = settings.accounts_dir
        self._accounts_dir.mkdir(parents=True, exist_ok=True)

    @property
    def default_account_id(self) -> str:
        return self._settings.default_account_id or self.DEFAULT_ACCOUNT_ID

    def ensure_default_account(self) -> AccountResponse:
        account = self.get_account(self.default_account_id)
        if account is not None:
            return account

        meta = AccountMeta(id=self.default_account_id, alias="Default account", status="warming")
        self._ensure_account_directories(meta.id)
        self.save_meta(meta)
        return self.get_account(meta.id)  # type: ignore[return-value]

    def list_accounts(self) -> list[AccountResponse]:
        self.ensure_default_account()
        items: list[AccountResponse] = []
        ids = {self.default_account_id}
        ids.update(path.name for path in self._accounts_dir.iterdir() if path.is_dir())
        for account_id in sorted(ids):
            account = self.get_account(account_id)
            if account is not None:
                items.append(account)
        items.sort(key=lambda item: (item.id != self.default_account_id, item.created_at))
        return items

    def create_account(self, alias: str | None = None, make_default: bool = False) -> AccountResponse:
        account_id = f"acc_{uuid.uuid4().hex[:12]}"
        meta = AccountMeta(id=account_id, alias=alias or account_id, status="warming")
        self._ensure_account_directories(account_id)
        self.save_meta(meta)
        if make_default:
            self._settings.default_account_id = account_id
        return self.get_account(account_id)  # type: ignore[return-value]

    def get_account(self, account_id: str) -> AccountResponse | None:
        meta = self.get_meta(account_id)
        if meta is None:
            return None
        storage_path = self.get_storage_state_path(account_id)
        return AccountResponse(
            **meta.model_dump(),
            has_storage_state=storage_path.exists() and storage_path.stat().st_size > 0,
            storage_state_path=str(storage_path),
            chrome_profile_path=str(self.get_chrome_profile_path(account_id)),
            is_default=(account_id == self.default_account_id),
        )

    def get_meta(self, account_id: str) -> AccountMeta | None:
        meta_path = self._get_meta_path(account_id)
        if not meta_path.exists():
            return None
        return AccountMeta.model_validate_json(meta_path.read_text(encoding='utf-8'))

    def save_meta(self, meta: AccountMeta) -> None:
        self._ensure_account_directories(meta.id)
        self._get_meta_path(meta.id).write_text(meta.model_dump_json(indent=2), encoding='utf-8')

    def update_status(self, account_id: str, status: AccountStatus, detail: str | None = None) -> AccountResponse:
        meta = self.get_meta(account_id)
        if meta is None:
            raise ValueError(f'Conta nao encontrada: {account_id}')
        meta.status = status
        if detail is not None:
            meta.last_error = detail
        self.save_meta(meta)
        return self.get_account(account_id)  # type: ignore[return-value]

    def touch_verified(self, account_id: str, detail: str | None = None, healthy: bool = True) -> AccountResponse:
        meta = self.get_meta(account_id)
        if meta is None:
            raise ValueError(f'Conta nao encontrada: {account_id}')
        from datetime import datetime, timezone

        meta.last_verified_at = datetime.now(timezone.utc)
        meta.last_error = detail
        if healthy and meta.status != 'disabled':
            meta.status = 'healthy'
        self.save_meta(meta)
        return self.get_account(account_id)  # type: ignore[return-value]

    def get_default_account(self) -> AccountResponse:
        configured = self.get_account(self.default_account_id)
        if configured is not None and configured.status != 'disabled':
            return configured
        accounts = [account for account in self.list_accounts() if account.status != 'disabled']
        if not accounts:
            return self.ensure_default_account()
        healthy = [account for account in accounts if account.status == 'healthy']
        return healthy[0] if healthy else accounts[0]

    def get_storage_state_path(self, account_id: str) -> Path:
        if account_id == self.default_account_id:
            return self._settings.storage_state_path
        return self._account_dir(account_id) / 'storage_state.json'

    def get_chrome_profile_path(self, account_id: str) -> Path:
        if account_id == self.default_account_id:
            return self._settings.storage_state_path.parent / 'chrome-profile'
        return self._account_dir(account_id) / 'chrome-profile'

    def _ensure_account_directories(self, account_id: str) -> None:
        self.get_storage_state_path(account_id).parent.mkdir(parents=True, exist_ok=True)
        self.get_chrome_profile_path(account_id).mkdir(parents=True, exist_ok=True)

    def _account_dir(self, account_id: str) -> Path:
        return self._accounts_dir / account_id

    def _get_meta_path(self, account_id: str) -> Path:
        if account_id == self.default_account_id:
            return self._settings.storage_state_path.parent / 'account-meta.json'
        return self._account_dir(account_id) / 'meta.json'
