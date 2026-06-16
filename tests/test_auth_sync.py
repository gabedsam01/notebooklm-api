"""Tests de isolamento por conta e ausencia de NOTEBOOKLM_HOME global (Onda 2)."""
from __future__ import annotations

import os
from pathlib import Path

from app.core.config import Settings
from app.main import create_app
from app.services.account_registry_service import AccountRegistryService


def test_create_app_does_not_set_notebooklm_home_global(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("NOTEBOOKLM_HOME", raising=False)
    data_dir = tmp_path / "data"
    settings = Settings(
        app_host="0.0.0.0",
        app_port=8080,
        data_dir=data_dir,
        notebooklm_mode="mock",
    )

    _ = create_app(settings)

    # Onda 2: o app nao depende mais de NOTEBOOKLM_HOME global; cada conta usa
    # seu storage_state explicito via from_storage(storage_path).
    assert "NOTEBOOKLM_HOME" not in os.environ


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
