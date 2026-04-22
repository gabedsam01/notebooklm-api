from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.models.notebooks import PersistedNotebook


class NotebookRepository:
    def __init__(self, sqlite_db_path: Path) -> None:
        self._db_path = sqlite_db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def upsert_notebook(
        self,
        notebook_id: str,
        title: str,
        source_count: int,
        artifact_count: int,
        origin: str,
        metadata: dict[str, Any] | None = None,
        account_id: str = "default",
    ) -> PersistedNotebook:
        now = _utc_now_iso()
        metadata_json = json.dumps(metadata or {}, ensure_ascii=False)

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO notebooks (
                    account_id, notebook_id, title, source_count, artifact_count, origin, metadata_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(account_id, notebook_id) DO UPDATE SET
                    title=excluded.title,
                    source_count=excluded.source_count,
                    artifact_count=excluded.artifact_count,
                    origin=excluded.origin,
                    metadata_json=excluded.metadata_json,
                    updated_at=excluded.updated_at
                """,
                (account_id, notebook_id, title, source_count, artifact_count, origin, metadata_json, now, now),
            )

        record = self.get_by_notebook_id(account_id, notebook_id)
        if record is None:
            raise RuntimeError("Falha ao persistir notebook")
        return record

    def get_by_notebook_id(self, account_id: str, notebook_id: str) -> PersistedNotebook | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM notebooks WHERE account_id = ? AND notebook_id = ?",
                (account_id, notebook_id),
            ).fetchone()
        return _row_to_model(row)

    def get_by_local_id(self, account_id: str, local_id: int) -> PersistedNotebook | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM notebooks WHERE account_id = ? AND id = ?",
                (account_id, local_id),
            ).fetchone()
        return _row_to_model(row)

    def list_all(self, account_id: str | None = None) -> list[PersistedNotebook]:
        with self._connect() as conn:
            if account_id is None:
                rows = conn.execute(
                    "SELECT * FROM notebooks ORDER BY updated_at DESC, id DESC"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM notebooks WHERE account_id = ? ORDER BY updated_at DESC, id DESC",
                    (account_id,),
                ).fetchall()
        return [item for item in (_row_to_model(row) for row in rows) if item is not None]

    def increment_artifact_count(self, account_id: str, notebook_id: str, amount: int = 1) -> None:
        now = _utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE notebooks
                SET artifact_count = artifact_count + ?, updated_at = ?
                WHERE account_id = ? AND notebook_id = ?
                """,
                (amount, now, account_id, notebook_id),
            )

    def delete_by_notebook_id(self, notebook_id: str, account_id: str = "default") -> tuple[bool, int | None]:
        existing = self.get_by_notebook_id(account_id, notebook_id)
        if existing is None:
            return False, None

        with self._connect() as conn:
            conn.execute("DELETE FROM notebooks WHERE account_id = ? AND notebook_id = ?", (account_id, notebook_id))
        return True, existing.local_id

    def delete_by_local_id(self, local_id: int, account_id: str = "default") -> tuple[bool, str | None]:
        existing = self.get_by_local_id(account_id, local_id)
        if existing is None:
            return False, None

        with self._connect() as conn:
            conn.execute("DELETE FROM notebooks WHERE account_id = ? AND id = ?", (account_id, local_id))
        return True, existing.notebook_id

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS notebooks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id TEXT NOT NULL DEFAULT 'default',
                    notebook_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    source_count INTEGER NOT NULL DEFAULT 0,
                    artifact_count INTEGER NOT NULL DEFAULT 0,
                    origin TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            cols = {row[1] for row in conn.execute("PRAGMA table_info(notebooks)").fetchall()}
            if "account_id" not in cols:
                conn.execute("ALTER TABLE notebooks ADD COLUMN account_id TEXT NOT NULL DEFAULT 'default'")
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_notebooks_account_notebook ON notebooks(account_id, notebook_id)"
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        return connection


def _row_to_model(row: sqlite3.Row | None) -> PersistedNotebook | None:
    if row is None:
        return None
    return PersistedNotebook(
        local_id=int(row["id"]),
        account_id=str(row["account_id"]),
        notebook_id=str(row["notebook_id"]),
        title=str(row["title"]),
        source_count=int(row["source_count"]),
        artifact_count=int(row["artifact_count"]),
        origin=str(row["origin"]),
        metadata=json.loads(str(row["metadata_json"] or "{}")),
        created_at=datetime.fromisoformat(str(row["created_at"])),
        updated_at=datetime.fromisoformat(str(row["updated_at"])),
    )


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
