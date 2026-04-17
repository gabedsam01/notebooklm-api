from __future__ import annotations

from dataclasses import dataclass
import logging

from app.models.notebooks import (
    NotebookDeleteResultResponse,
    NotebookResponse,
    NotebookSyncResponse,
    PersistedNotebook,
)
from app.services.notebook_repository import NotebookRepository
from app.services.notebooklm_service import NotebookLMService

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class NotebookResolveResult:
    notebook_id: str
    local_id: int | None


class NotebookCatalogService:
    def __init__(self, repository: NotebookRepository, notebook_service: NotebookLMService) -> None:
        self._repository = repository
        self._notebook_service = notebook_service

    async def create_and_persist(self, title: str) -> NotebookResponse:
        notebook_id = await self._notebook_service.create_notebook(title)
        remote = await self._notebook_service.get_notebook(notebook_id)
        record = self._repository.upsert_notebook(
            notebook_id=notebook_id,
            title=str((remote or {}).get("title", title)),
            source_count=int((remote or {}).get("source_count", 0)),
            artifact_count=0,
            origin="local_created",
            metadata=remote or {},
        )
        return NotebookResponse(**record.model_dump())

    async def refresh_and_get(self, notebook_id: str) -> NotebookResponse | None:
        remote = await self._notebook_service.get_notebook(notebook_id)
        if remote is None:
            local = self._repository.get_by_notebook_id(notebook_id)
            return NotebookResponse(**local.model_dump()) if local else None

        existing = self._repository.get_by_notebook_id(notebook_id)
        record = self._repository.upsert_notebook(
            notebook_id=notebook_id,
            title=str(remote.get("title", "Notebook")),
            source_count=int(remote.get("source_count", 0)),
            artifact_count=(existing.artifact_count if existing else 0),
            origin=(existing.origin if existing else "imported_from_account"),
            metadata=remote,
        )
        return NotebookResponse(**record.model_dump())

    def list_persisted(self) -> list[PersistedNotebook]:
        return self._repository.list_all()

    async def sync_from_account(self) -> NotebookSyncResponse:
        account_items = await self._notebook_service.list_notebooks()
        local_items = self._repository.list_all()
        local_map = {item.notebook_id: item for item in local_items}

        imported_count = 0
        for item in account_items:
            notebook_id = str(item.get("id") or item.get("notebook_id") or "").strip()
            if not notebook_id:
                continue
            title = str(item.get("title") or "Notebook")
            source_count = int(item.get("source_count") or 0)
            existing = local_map.get(notebook_id)
            self._repository.upsert_notebook(
                notebook_id=notebook_id,
                title=title,
                source_count=source_count,
                artifact_count=(existing.artifact_count if existing else 0),
                origin=(existing.origin if existing else "imported_from_account"),
                metadata=item,
            )
            if existing is None:
                imported_count += 1

        account_ids = {
            str(item.get("id") or item.get("notebook_id") or "").strip()
            for item in account_items
            if str(item.get("id") or item.get("notebook_id") or "").strip()
        }
        stale_local_items = [item for item in local_items if item.notebook_id not in account_ids]
        stale_local_count = 0
        for item in stale_local_items:
            deleted, _ = self._repository.delete_by_notebook_id(item.notebook_id)
            if deleted:
                stale_local_count += 1

        return NotebookSyncResponse(
            found_in_account=len(account_ids),
            imported_count=imported_count,
            stale_local_count=stale_local_count,
            detail=(
                "Sincronizacao concluida. "
                f"Adicionados: {imported_count}. Removidos: {stale_local_count}."
            ),
        )

    def resolve_notebook_id(self, notebook_id: str | None, local_id: int | None) -> NotebookResolveResult:
        if notebook_id:
            local = self._repository.get_by_notebook_id(notebook_id)
            return NotebookResolveResult(
                notebook_id=notebook_id,
                local_id=(local.local_id if local else None),
            )

        if local_id is None:
            raise ValueError("Informe notebook_id ou local_id")

        local = self._repository.get_by_local_id(local_id)
        if local is None:
            raise ValueError("local_id nao encontrado")
        return NotebookResolveResult(notebook_id=local.notebook_id, local_id=local.local_id)

    def increment_artifact_count(self, notebook_id: str) -> None:
        self._repository.increment_artifact_count(notebook_id)

    async def delete_notebook(
        self,
        notebook_id: str | None = None,
        local_id: int | None = None,
    ) -> NotebookDeleteResultResponse:
        if not notebook_id and local_id is None:
            raise ValueError("Informe notebook_id ou local_id")

        local_record = None
        resolved_notebook_id: str | None = notebook_id

        if local_id is not None:
            local_record = self._repository.get_by_local_id(local_id)
            if local_record is not None:
                resolved_notebook_id = local_record.notebook_id

        if resolved_notebook_id:
            if local_record is None:
                local_record = self._repository.get_by_notebook_id(resolved_notebook_id)
        elif local_record is not None:
            resolved_notebook_id = local_record.notebook_id

        if resolved_notebook_id is None:
            return NotebookDeleteResultResponse(
                status="failed",
                notebook_id="",
                local_id=local_id,
                deleted_remote=False,
                deleted_local=False,
                detail="Nao foi possivel resolver notebook_id a partir de local_id.",
            )

        deleted_remote = False
        deleted_local = False
        detail_parts: list[str] = []

        try:
            remote = await self._notebook_service.get_notebook(resolved_notebook_id)
            if remote is None:
                detail_parts.append("Notebook remoto ja estava ausente")
            else:
                await self._notebook_service.delete_notebook(resolved_notebook_id)
                deleted_remote = True
                detail_parts.append("Notebook remoto removido")
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Falha ao remover notebook remoto %s: %s",
                resolved_notebook_id,
                exc.__class__.__name__,
            )
            detail_parts.append(f"Falha ao remover remoto: {exc.__class__.__name__}")

        if local_record is not None:
            deleted_local, _ = self._repository.delete_by_notebook_id(local_record.notebook_id)
            if deleted_local:
                detail_parts.append("Registro local removido")
        elif local_id is not None:
            deleted_local, _ = self._repository.delete_by_local_id(local_id)
            if deleted_local:
                detail_parts.append("Registro local removido")
        else:
            detail_parts.append("Registro local nao encontrado")

        status_label = "completed"
        if not deleted_remote and not deleted_local:
            status_label = "failed" if any("Falha" in part for part in detail_parts) else "completed_with_warnings"
        elif not deleted_remote or not deleted_local:
            status_label = "completed_with_warnings"

        return NotebookDeleteResultResponse(
            status=status_label,
            notebook_id=resolved_notebook_id,
            local_id=(local_record.local_id if local_record else local_id),
            deleted_remote=deleted_remote,
            deleted_local=deleted_local,
            detail="; ".join(detail_parts) if detail_parts else "Operacao concluida.",
        )
