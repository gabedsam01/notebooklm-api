from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from app.models.auth import StorageStatePayload


class StorageStateService:
    def __init__(self, storage_state_path: Path) -> None:
        self._storage_state_path = storage_state_path

    @property
    def storage_state_path(self) -> Path:
        return self._storage_state_path

    def exists(self) -> bool:
        return self._storage_state_path.is_file() and self._storage_state_path.stat().st_size > 0

    def load(self) -> dict[str, Any] | None:
        if not self.exists():
            return None
        return json.loads(self._storage_state_path.read_text(encoding="utf-8"))

    def save(self, payload: StorageStatePayload | dict[str, Any]) -> None:
        validated_payload = StorageStatePayload.model_validate(payload)
        self._storage_state_path.parent.mkdir(parents=True, exist_ok=True)

        temp_path = self._storage_state_path.with_suffix(".tmp")
        temp_path.write_text(
            json.dumps(validated_payload.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.chmod(temp_path, 0o600)
        temp_path.replace(self._storage_state_path)
        os.chmod(self._storage_state_path, 0o600)
