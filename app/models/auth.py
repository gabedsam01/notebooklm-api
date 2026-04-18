from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StorageCookie(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = Field(min_length=1)
    value: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    path: str = Field(default="/", min_length=1)
    expires: int | float | None = None
    httpOnly: bool | None = None
    secure: bool | None = None
    sameSite: Literal["Lax", "None", "Strict"] | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Normalize expirationDate to expires
            if "expirationDate" in data and "expires" not in data:
                data["expires"] = data["expirationDate"]
            
            # Normalize sameSite
            same_site = data.get("sameSite")
            if isinstance(same_site, str):
                lower_ss = same_site.lower()
                if lower_ss in ("no_restriction", "none"):
                    data["sameSite"] = "None"
                elif lower_ss == "lax":
                    data["sameSite"] = "Lax"
                elif lower_ss == "strict":
                    data["sameSite"] = "Strict"
                else:
                    data.pop("sameSite", None)
        return data


class StorageStatePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    cookies: list[StorageCookie] = Field(default_factory=list)
    origins: list[dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def normalize_list_to_dict(cls, data: Any) -> Any:
        if isinstance(data, list):
            return {"cookies": data, "origins": []}
        return data


class StorageStateSaveResponse(BaseModel):
    storage_state_present: bool
    storage_state_valid: bool
    cookie_count_received: int
    cookie_count_kept: int
    kept_cookie_names: list[str]
    has_minimum_auth_cookies: bool
    notebooklm_access_ok: bool
    detail: str


class AuthStatusResponse(BaseModel):
    storage_state_present: bool
    storage_state_valid: bool = False
    cookie_count: int = 0
    notebooklm_access_ok: bool
    detail: str


class LoginStartResponse(BaseModel):
    session_id: str
    expires_at: datetime
    detail: str


class LoginCompleteRequest(BaseModel):
    session_id: str = Field(min_length=8)
    storage_state: StorageStatePayload


class LoginCompleteResponse(BaseModel):
    completed: bool
    detail: str
