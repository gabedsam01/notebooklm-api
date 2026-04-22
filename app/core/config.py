from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore',
    )

    app_name: str = 'NotebookLM API'
    app_env: str = 'dev'
    app_version: str = '0.1.0'
    log_level: str = 'INFO'
    app_host: str = '0.0.0.0'
    app_port: int = Field(default=8080, ge=1, le=65535)

    data_dir: Path = Path('data')
    jobs_dir: Path | None = None
    artifacts_dir: Path | None = None
    temp_dir: Path | None = None
    storage_state_path: Path | None = Field(
        default=None,
        validation_alias=AliasChoices(
            'storage_state_path',
            'STORAGE_STATE_PATH',
            'NOTEBOOKLM_STORAGE_STATE_PATH',
        ),
    )
    accounts_dir: Path | None = None
    default_account_id: str = 'default'
    account_keepalive_interval_seconds: float = Field(default=0.0, ge=0.0)
    templates_dir: Path = Path('app/templates')
    static_dir: Path = Path('app/static')

    notebooklm_mode: Literal['mock', 'real'] = 'real'
    notebook_operation_timeout_seconds: int = Field(default=240, ge=5)
    notebook_poll_interval_seconds: float = Field(default=2.0, ge=0.2)

    artifact_wait_timeout_seconds: int = Field(default=1800, ge=1)
    artifact_poll_interval_seconds: float = Field(default=15.0, ge=0.05)
    audio_wait_timeout_seconds: int | None = None
    video_wait_timeout_seconds: int | None = None

    worker_poll_interval_seconds: float = Field(default=0.2, ge=0.01)
    sqlite_db_path: Path | None = None

    @field_validator(
        'data_dir',
        'jobs_dir',
        'artifacts_dir',
        'temp_dir',
        'storage_state_path',
        'accounts_dir',
        'sqlite_db_path',
        'templates_dir',
        'static_dir',
        mode='before',
    )
    @classmethod
    def _coerce_to_path(cls, value: object) -> object:
        if value is None or isinstance(value, Path):
            return value
        return Path(str(value))

    @model_validator(mode='after')
    def _resolve_directories(self) -> 'Settings':
        if self.jobs_dir is None:
            self.jobs_dir = self.data_dir / 'jobs'
        if self.artifacts_dir is None:
            self.artifacts_dir = self.data_dir / 'artifacts'
        if self.temp_dir is None:
            self.temp_dir = self.data_dir / 'tmp'
        if self.storage_state_path is None:
            self.storage_state_path = self.data_dir / 'auth' / 'storage_state.json'
        if self.accounts_dir is None:
            self.accounts_dir = self.data_dir / 'accounts'
        if self.sqlite_db_path is None:
            self.sqlite_db_path = self.data_dir / 'notebooks.db'

        self.data_dir = self.data_dir.resolve()
        self.jobs_dir = self.jobs_dir.resolve()
        self.artifacts_dir = self.artifacts_dir.resolve()
        self.temp_dir = self.temp_dir.resolve()
        self.storage_state_path = self.storage_state_path.resolve()
        self.accounts_dir = self.accounts_dir.resolve()
        self.sqlite_db_path = self.sqlite_db_path.resolve()
        self.templates_dir = self.templates_dir.resolve()
        self.static_dir = self.static_dir.resolve()
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
