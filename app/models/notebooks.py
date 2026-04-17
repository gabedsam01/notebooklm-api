from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator


class NotebookTarget(BaseModel):
    notebook_id: str | None = Field(default=None, min_length=1)
    local_id: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _ensure_target(self) -> "NotebookTarget":
        if not self.notebook_id and self.local_id is None:
            raise ValueError("Informe notebook_id ou local_id")
        return self


class NotebookCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class PersistedNotebook(BaseModel):
    local_id: int
    notebook_id: str
    title: str
    source_count: int = 0
    artifact_count: int = 0
    origin: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class NotebookResponse(PersistedNotebook):
    pass


class NotebookDeleteResponse(BaseModel):
    deleted: bool
    notebook_id: str


class NotebookDeleteResultResponse(BaseModel):
    status: str
    notebook_id: str
    local_id: int | None = None
    deleted_remote: bool
    deleted_local: bool
    detail: str


class NotebookListResponse(BaseModel):
    count: int
    items: list[PersistedNotebook]


class NotebookSyncResponse(BaseModel):
    found_in_account: int
    imported_count: int
    stale_local_count: int
    detail: str
