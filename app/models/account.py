
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

AccountStatus = Literal[
    "healthy",
    "warming",
    "degraded",
    "challenge_required",
    "expired",
    "disabled",
]


class AccountMeta(BaseModel):
    id: str
    alias: str | None = None
    status: AccountStatus = "warming"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_verified_at: datetime | None = None
    last_error: str | None = None


class AccountCreateRequest(BaseModel):
    alias: str | None = Field(default=None, max_length=200)
    make_default: bool = False


class AccountUpdateStatusRequest(BaseModel):
    detail: str | None = Field(default=None, max_length=1_000)


class AccountResponse(AccountMeta):
    has_storage_state: bool
    storage_state_path: str
    chrome_profile_path: str
    is_default: bool = False
