"""Tests para sincronização base de NOTEBOOKLM_HOME e multi-account auth paths."""
from __future__ import annotations

import os
from pathlib import Path

from app.core.config import Settings
from app.main import create_app
from app.services.account_registry_service import AccountRegistryService


def test_notebooklm_home_synced_on_app_creation(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    settings = Settings(
        app_host="0.0.0.0",
        app_port=8080,
        data_dir=data_dir,
        notebooklm_mode="mock",
    )

    _ = create_app(settings)

    expected_auth_dir = str(settings.storage_state_path.parent)
    assert os.environ.get("NOTEBOOKLM_HOME") == expected_auth_dir


def test_account_registry_uses_per_account_storage_paths(tmp_path: Path) -> None:
    settings = Settings(
        app_host="0.0.0.0",
        app_port=8080,
        data_dir=tmp_path / "data",
        notebooklm_mode="mock",
    )
    registry = AccountRegistryService(settings)
    registry.ensure_default_account()
    other = registry.create_account(alias="teste")

    assert registry.get_storage_state_path("default") == settings.storage_state_path
    assert registry.get_storage_state_path(other.id).parent == settings.accounts_dir / other.id
    assert registry.get_chrome_profile_path(other.id).name == "chrome-profile"
