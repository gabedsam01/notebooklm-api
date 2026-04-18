"""Tests para sincronização de NOTEBOOKLM_HOME com o diretório de auth do app."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.core.config import Settings
from app.main import create_app


def test_notebooklm_home_synced_on_app_creation(tmp_path: Path) -> None:
    """Após create_app(), NOTEBOOKLM_HOME deve apontar para o diretório pai do storage_state_path."""
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


def test_notebooklm_home_uses_custom_storage_state_path(tmp_path: Path) -> None:
    """Se storage_state_path for customizado, NOTEBOOKLM_HOME deve refletir."""
    custom_auth_dir = tmp_path / "custom" / "auth"
    custom_auth_dir.mkdir(parents=True)
    custom_storage = custom_auth_dir / "storage_state.json"

    settings = Settings(
        app_host="0.0.0.0",
        app_port=8080,
        data_dir=tmp_path / "data",
        storage_state_path=custom_storage,
        notebooklm_mode="mock",
    )

    _ = create_app(settings)

    assert os.environ.get("NOTEBOOKLM_HOME") == str(custom_auth_dir)
