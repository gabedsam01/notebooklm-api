from __future__ import annotations

import asyncio
import json
import logging
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import TypeAdapter

from app.core.config import Settings
from app.models.jobs import (
    AddSourceJobRequest,
    AddSourcesBatchJobRequest,
    ArtifactMetadata,
    CreateNotebookJobRequest,
    GenerateAudioSummaryJobRequest,
    GenerateVideoSummaryJobRequest,
    JobLogEntry,
    JobRecord,
    JobRequest,
    JobStatus,
    JobType,
)
from app.services.artifact_service import ArtifactService
from app.services.job_repository import JobRepository
from app.services.notebook_catalog_service import NotebookCatalogService
from app.services.notebooklm_service import NotebookLMService
from app.services.source_builder_service import SourceBuilderService
from app.utils.error_sanitizer import sanitize_exception

logger = logging.getLogger(__name__)


class JobService:
    def __init__(
        self,
        settings: Settings,
        repository: JobRepository,
        notebook_service: NotebookLMService,
        source_builder: SourceBuilderService,
        artifact_service: ArtifactService,
        notebook_catalog: NotebookCatalogService,
    ) -> None:
        self._settings = settings
        self._repository = repository
        self._notebook_service = notebook_service
        self._source_builder = source_builder
        self._artifact_service = artifact_service
        self._notebook_catalog = notebook_catalog
        self._threads: dict[str, threading.Thread] = {}
        self._threads_lock = threading.Lock()
        self._job_request_adapter = TypeAdapter(JobRequest)

    async def submit_job(self, payload: JobRequest) -> JobRecord:
        prepared_payload = self._prepare_payload(payload)
        now = _utc_now()
        job_id = uuid4().hex
        resolved_name = prepared_payload.name or f"{prepared_payload.type}-{job_id[:8]}"

        notebook_id = getattr(prepared_payload, "notebook_id", None)
        job = JobRecord(
            id=job_id,
            name=resolved_name,
            type=JobType(prepared_payload.type),
            status=JobStatus.queued,
            input=prepared_payload.model_dump(mode="json", exclude={"name"}),
            result=None,
            error=None,
            created_at=now,
            started_at=None,
            completed_at=None,
            updated_at=now,
            duration_ms=None,
            notebook_id=notebook_id,
            artifact_path=None,
            artifact_metadata=None,
            logs=[],
        )
        self._append_log(job, stage="queued", message="job enfileirado")

        thread = threading.Thread(
            target=self._run_job_in_thread,
            args=(job.id, prepared_payload.model_dump(mode="json")),
            daemon=True,
            name=f"job-{job.id[:8]}",
        )
        with self._threads_lock:
            self._threads[job.id] = thread
        thread.start()
        return job

    def get_job(self, job_id: str) -> JobRecord | None:
        return self._repository.get(job_id)

    def list_jobs(self, job_id: str | None = None, name: str | None = None) -> list[JobRecord]:
        return self._repository.list(job_id=job_id, name=name)

    def resolve_artifact_path(self, job: JobRecord) -> Path | None:
        return self._artifact_service.resolve_job_artifact_path(job)

    async def shutdown(self) -> None:
        with self._threads_lock:
            threads = list(self._threads.values())
        for thread in threads:
            thread.join(timeout=0.5)

    async def generate_audio_sync(
        self,
        notebook_id: str,
        mode: str,
        language: str,
        duration: str,
        focus_prompt: str,
    ) -> tuple[Path, ArtifactMetadata, dict[str, Any]]:
        request_id = f"sync-audio-{uuid4().hex}"
        artifact_reference = await self._notebook_service.generate_audio_summary(
            notebook_id=notebook_id,
            mode=mode,
            language=language,
            duration=duration,
            focus_prompt=focus_prompt,
        )
        timeout_seconds = (
            self._settings.audio_wait_timeout_seconds 
            if self._settings.audio_wait_timeout_seconds is not None 
            else self._settings.artifact_wait_timeout_seconds
        )
        poll_interval = self._settings.artifact_poll_interval_seconds

        try:
            final_reference = await self._notebook_service.wait_for_artifact(
                notebook_id=notebook_id,
                artifact_reference=artifact_reference,
                timeout_seconds=timeout_seconds,
                poll_interval_seconds=poll_interval,
            )
        except TimeoutError:
            final_reference = await self._find_ready_artifact_fallback(notebook_id, "audio")
            if not final_reference:
                raise

        import re
        artifact_title = await self._get_artifact_title(notebook_id, final_reference)
        safe_title = re.sub(r'[^a-zA-Z0-9_\-]', '_', artifact_title) if artifact_title else request_id
        destination = self._artifact_service.build_path(safe_title, ".wav")
        
        saved = await self._download_with_retry(
            notebook_id=notebook_id,
            artifact_reference=final_reference,
            destination_path=destination,
            media_type="audio",
        )
        metadata = self._artifact_service.build_metadata(saved, content_type="audio/wav")
        if artifact_title:
            metadata.title = artifact_title
        self._notebook_catalog.increment_artifact_count(notebook_id)
        return saved, metadata, {"artifact_reference": final_reference}

    async def generate_video_sync(
        self,
        notebook_id: str,
        mode: str,
        style: str,
        language: str,
        visual_style: str | None,
        focus_prompt: str,
    ) -> tuple[Path, ArtifactMetadata, dict[str, Any]]:
        request_id = f"sync-video-{uuid4().hex}"
        artifact_reference = await self._notebook_service.generate_video_summary(
            notebook_id=notebook_id,
            mode=mode,
            style=style,
            language=language,
            visual_style=visual_style,
            focus_prompt=focus_prompt,
        )
        timeout_seconds = (
            self._settings.video_wait_timeout_seconds 
            if self._settings.video_wait_timeout_seconds is not None 
            else self._settings.artifact_wait_timeout_seconds
        )
        poll_interval = self._settings.artifact_poll_interval_seconds

        try:
            final_reference = await self._notebook_service.wait_for_artifact(
                notebook_id=notebook_id,
                artifact_reference=artifact_reference,
                timeout_seconds=timeout_seconds,
                poll_interval_seconds=poll_interval,
            )
        except TimeoutError:
            final_reference = await self._find_ready_artifact_fallback(notebook_id, "video")
            if not final_reference:
                raise

        import re
        artifact_title = await self._get_artifact_title(notebook_id, final_reference)
        safe_title = re.sub(r'[^a-zA-Z0-9_\-]', '_', artifact_title) if artifact_title else request_id
        destination = self._artifact_service.build_path(safe_title, ".mp4")
        
        saved = await self._download_with_retry(
            notebook_id=notebook_id,
            artifact_reference=final_reference,
            destination_path=destination,
            media_type="video",
        )
        metadata = self._artifact_service.build_metadata(saved, content_type="video/mp4")
        if artifact_title:
            metadata.title = artifact_title
        self._notebook_catalog.increment_artifact_count(notebook_id)
        return saved, metadata, {"artifact_reference": final_reference}

    async def _download_with_retry(
        self,
        notebook_id: str,
        artifact_reference: str,
        destination_path: Path,
        media_type: str,
        max_attempts: int = 3,
        base_delay: float = 2.0,
    ) -> Path:
        """Download com retry e backoff exponencial.

        Trata ``ArtifactNotReadyError`` e erros transientes de rede
        com backoff ``2s → 4s → 8s`` entre tentativas.

        Isso cobre a race condition onde ``poll_status`` retorna
        ``completed`` mas as URLs de mídia ainda não estão populadas.
        """
        last_exc: Exception | None = None

        for attempt in range(1, max_attempts + 1):
            try:
                return await self._notebook_service.download_artifact(
                    notebook_id=notebook_id,
                    artifact_reference=artifact_reference,
                    destination_path=destination_path,
                    media_type=media_type,
                )
            except Exception as exc:
                last_exc = exc
                if attempt < max_attempts:
                    delay = base_delay * (2 ** (attempt - 1))  # 2s, 4s, 8s
                    logger.warning(
                        "Download attempt %d/%d failed (%s): %s. Retrying in %.1fs...",
                        attempt,
                        max_attempts,
                        media_type,
                        sanitize_exception(exc),
                        delay,
                    )
                    await asyncio.sleep(delay)

        raise last_exc  # type: ignore[misc]

    async def _find_ready_artifact_fallback(self, notebook_id: str, media_type: str) -> str | None:
        """Busca o artefato mais recente pronto (completed) com o media_type especificado."""
        try:
            artifacts = await self._notebook_service.list_artifacts(notebook_id)
            ready = [a for a in artifacts if a.get("is_completed") and a.get("media_type") == media_type]
            if not ready:
                return None
            ready.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            return ready[0].get("id")
        except Exception as exc:
            logger.warning("Falha ao buscar artefatos para fallback: %s", sanitize_exception(exc))
            return None

    async def _get_artifact_title(self, notebook_id: str, artifact_id: str) -> str | None:
        try:
            artifacts = await self._notebook_service.list_artifacts(notebook_id)
            for a in artifacts:
                if a.get("id") == artifact_id:
                    return a.get("title")
        except Exception:
            pass
        return None

    async def sync_notebook_artifacts(self, notebook_id: str) -> int:
        """Puxa artefatos remotos existentes do notebook e cria JobRecords locais."""
        try:
            artifacts = await self._notebook_service.list_artifacts(notebook_id)
        except Exception as exc:
            logger.warning("Falha ao listar artefatos do notebook %s: %s", notebook_id, sanitize_exception(exc))
            return 0
        
        imported = 0
        for a in artifacts:
            if not a.get("is_completed"):
                continue
                
            job_id = a.get("id")
            if not job_id:
                continue
                
            existing = self._repository.get(job_id)
            if existing:
                continue
                
            media_type = a.get("media_type")
            job_type = JobType.generate_audio_summary if media_type == "audio" else JobType.generate_video_summary
            
            job = JobRecord(
                id=job_id,
                name=a.get("title") or f"Sincronizado {job_id[:8]}",
                type=job_type,
                status=JobStatus.completed,
                input={"origin": "sync"},
                result={"artifact_reference": job_id},
                created_at=_utc_now(),
                updated_at=_utc_now(),
                notebook_id=notebook_id,
            )
            self._repository.save(job)
            self._notebook_catalog.increment_artifact_count(notebook_id)
            imported += 1
            
        return imported

    async def trigger_artifact_download(self, job_id: str) -> bool:
        """Dispara o download de um artefato remoto em background."""
        job = self._repository.get(job_id)
        if not job or job.artifact_path or not job.result:
            return False
            
        reference = job.result.get("artifact_reference")
        if not reference or not job.notebook_id:
            return False
            
        self._update_job(job, status=JobStatus.running)
        self._append_log(job, stage="download", message="Iniciando download em background...")
        
        import asyncio
        asyncio.create_task(self._background_download(job, reference))
        return True

    async def _background_download(self, job: JobRecord, reference: str) -> None:
        try:
            import re
            artifact_title = await self._get_artifact_title(job.notebook_id, reference)
            safe_title = re.sub(r'[^a-zA-Z0-9_\-]', '_', artifact_title) if artifact_title else job.id
            
            ext = ".wav" if job.type == JobType.generate_audio_summary else ".mp4"
            destination = self._artifact_service.build_path(safe_title, ext)
            
            media_type = "audio" if ext == ".wav" else "video"
            saved = await self._download_with_retry(
                notebook_id=job.notebook_id,
                artifact_reference=reference,
                destination_path=destination,
                media_type=media_type,
            )
            
            metadata = self._artifact_service.build_metadata(saved, content_type=f"{media_type}/{ext[1:]}")
            if artifact_title:
                metadata.title = artifact_title
                
            self._update_job(
                job,
                status=JobStatus.completed,
                artifact_path=str(destination),
                artifact_metadata=metadata,
            )
            self._append_log(job, stage="download", message="Download concluido com sucesso.")
        except Exception as exc:
            self._update_job(job, status=JobStatus.failed, error=str(exc))
            self._append_log(job, stage="error", message=f"Falha no download: {exc}")

    def _prepare_payload(self, payload: JobRequest) -> JobRequest:
        if isinstance(payload, CreateNotebookJobRequest):
            return payload

        if hasattr(payload, "notebook_id") or hasattr(payload, "local_id"):
            resolved = self._notebook_catalog.resolve_notebook_id(
                notebook_id=getattr(payload, "notebook_id", None),
                local_id=getattr(payload, "local_id", None),
            )
            return payload.model_copy(update={"notebook_id": resolved.notebook_id, "local_id": resolved.local_id})

        return payload

    def _run_job_in_thread(self, job_id: str, payload_data: dict[str, Any]) -> None:
        try:
            payload = self._job_request_adapter.validate_python(payload_data)
            asyncio.run(self._run_job(job_id, payload))
        finally:
            with self._threads_lock:
                self._threads.pop(job_id, None)

    async def _run_job(self, job_id: str, payload: JobRequest) -> None:
        temp_dir = self._settings.temp_dir / job_id
        temp_dir.mkdir(parents=True, exist_ok=True)
        self._persist_temp_payload(temp_dir, payload)

        job = self._repository.get(job_id)
        if job is None:
            return

        try:
            self._update_job(job, status=JobStatus.running, started_at=_utc_now())
            self._append_log(job, stage="running", message="job em execucao")

            if isinstance(payload, CreateNotebookJobRequest):
                self._append_log(job, stage="creating_notebook", message="criando notebook...")
                notebook = await self._notebook_catalog.create_and_persist(payload.title)
                self._append_log(job, stage="creating_notebook", message="notebook criado")
                self._complete_job(
                    job,
                    notebook_id=notebook.notebook_id,
                    result={"notebook_id": notebook.notebook_id, "local_id": notebook.local_id},
                )
                return

            if isinstance(payload, AddSourceJobRequest):
                self._append_log(job, stage="adding_source", message="adicionando fonte...")
                source = self._source_builder.normalize_single(payload.title, payload.content)
                source_id = await self._notebook_service.add_text_source(
                    notebook_id=str(payload.notebook_id),
                    title=source.title,
                    content=source.content,
                )
                await self._notebook_catalog.refresh_and_get(str(payload.notebook_id))
                self._append_log(job, stage="adding_source", message="fonte adicionada")
                self._complete_job(
                    job,
                    notebook_id=str(payload.notebook_id),
                    result={"added_count": 1, "source_ids": [source_id] if source_id else []},
                )
                return

            if isinstance(payload, AddSourcesBatchJobRequest):
                self._append_log(job, stage="adding_sources_batch", message="adicionando fontes em lote...")
                sources = self._source_builder.normalize_batch(payload.sources)
                source_ids = await self._notebook_service.add_text_sources_batch(
                    notebook_id=str(payload.notebook_id),
                    sources=[source.model_dump() for source in sources],
                )
                await self._notebook_catalog.refresh_and_get(str(payload.notebook_id))
                self._append_log(job, stage="adding_sources_batch", message="lote de fontes adicionado")
                self._complete_job(
                    job,
                    notebook_id=str(payload.notebook_id),
                    result={"added_count": len(sources), "source_ids": source_ids},
                )
                return

            if isinstance(payload, GenerateAudioSummaryJobRequest):
                await self._run_audio_summary_job(job, payload)
                return

            if isinstance(payload, GenerateVideoSummaryJobRequest):
                await self._run_video_summary_job(job, payload)
                return

            if payload.type == JobType.delete_notebook.value:
                notebook_id = str(getattr(payload, "notebook_id"))
                self._append_log(job, stage="deleting_notebook", message="deletando notebook...")
                delete_result = await self._notebook_catalog.delete_notebook(notebook_id=notebook_id)
                self._append_log(job, stage="deleting_notebook", message=delete_result.detail)
                self._complete_job(
                    job,
                    notebook_id=notebook_id,
                    result=delete_result.model_dump(mode="json"),
                )
                return

            raise ValueError(f"Tipo de job nao suportado: {payload.type}")
        except Exception as exc:  # noqa: BLE001
            safe_error = sanitize_exception(exc)
            logger.exception("Job %s falhou: %s", job.id, safe_error)
            self._append_log(job, stage="failed", message=f"erro: {safe_error}")
            self._update_job(
                job,
                status=JobStatus.failed,
                error=safe_error,
                completed_at=_utc_now(),
            )
            self._apply_duration(job)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
            if job := self._repository.get(job_id):
                self._append_log(job, stage="cleanup", message="limpeza concluida")

    async def _run_audio_summary_job(
        self,
        job: JobRecord,
        payload: GenerateAudioSummaryJobRequest,
    ) -> None:
        notebook_id = str(payload.notebook_id)
        self._append_log(job, stage="generate_audio", message="gerando audio...")
        artifact_reference = await self._notebook_service.generate_audio_summary(
            notebook_id=notebook_id,
            mode=payload.mode.value,
            language=payload.language,
            duration=payload.duration.value,
            focus_prompt=payload.focus_prompt,
        )
        timeout_seconds = (
            self._settings.audio_wait_timeout_seconds 
            if self._settings.audio_wait_timeout_seconds is not None 
            else self._settings.artifact_wait_timeout_seconds
        )
        poll_interval = self._settings.artifact_poll_interval_seconds

        def status_updater(status: str) -> None:
            if status not in ("completed", "failed"):
                self._update_job(job, status=JobStatus.waiting_remote)
            self._append_log(job, stage="waiting_remote", message=f"status remoto: {status}")

        self._append_log(job, stage="generate_audio", message="aguardando artefato de audio...")
        self._update_job(job, status=JobStatus.waiting_remote)
        
        try:
            final_reference = await self._notebook_service.wait_for_artifact(
                notebook_id=notebook_id,
                artifact_reference=artifact_reference,
                timeout_seconds=timeout_seconds,
                poll_interval_seconds=poll_interval,
                status_callback=status_updater,
            )
        except TimeoutError as exc:
            self._append_log(job, stage="timed_out", message=str(exc))
            self._append_log(job, stage="fallback", message="tentando fallback por descoberta de artefato...")
            final_reference = await self._find_ready_artifact_fallback(notebook_id, "audio")
            if not final_reference:
                self._update_job(job, status=JobStatus.timed_out, error=str(exc))
                raise
            self._append_log(job, stage="fallback", message=f"fallback funcionou: artefato {final_reference} encontrado")

        self._append_log(job, stage="download_audio", message="baixando artefato de audio...")
        
        import re
        artifact_title = await self._get_artifact_title(notebook_id, final_reference)
        safe_title = re.sub(r'[^a-zA-Z0-9_\-]', '_', artifact_title) if artifact_title else job.id
        artifact_path = self._artifact_service.build_path(safe_title, ".wav")
        
        downloaded_path = await self._download_with_retry(
            notebook_id=notebook_id,
            artifact_reference=final_reference,
            destination_path=artifact_path,
            media_type="audio",
        )
        metadata = self._artifact_service.build_metadata(downloaded_path, content_type="audio/wav")
        if artifact_title:
            metadata.title = artifact_title
        self._notebook_catalog.increment_artifact_count(notebook_id)

        self._append_log(job, stage="download_audio", message="artefato de audio disponivel")
        self._complete_job(
            job,
            notebook_id=notebook_id,
            artifact_path=_relative_to_data_dir(self._settings.data_dir, downloaded_path),
            artifact_metadata=metadata,
            result={"artifact_reference": final_reference, "media_type": "audio/wav"},
            error=None,
        )

    async def _run_video_summary_job(
        self,
        job: JobRecord,
        payload: GenerateVideoSummaryJobRequest,
    ) -> None:
        notebook_id = str(payload.notebook_id)
        self._append_log(job, stage="generate_video", message="gerando video...")
        artifact_reference = await self._notebook_service.generate_video_summary(
            notebook_id=notebook_id,
            mode=payload.mode.value,
            style=payload.style.value,
            language=payload.language,
            visual_style=payload.visual_style,
            focus_prompt=payload.focus_prompt,
        )
        timeout_seconds = (
            self._settings.video_wait_timeout_seconds 
            if self._settings.video_wait_timeout_seconds is not None 
            else self._settings.artifact_wait_timeout_seconds
        )
        poll_interval = self._settings.artifact_poll_interval_seconds

        def status_updater(status: str) -> None:
            if status not in ("completed", "failed"):
                self._update_job(job, status=JobStatus.waiting_remote)
            self._append_log(job, stage="waiting_remote", message=f"status remoto: {status}")

        self._append_log(job, stage="generate_video", message="aguardando artefato de video...")
        self._update_job(job, status=JobStatus.waiting_remote)
        
        try:
            final_reference = await self._notebook_service.wait_for_artifact(
                notebook_id=notebook_id,
                artifact_reference=artifact_reference,
                timeout_seconds=timeout_seconds,
                poll_interval_seconds=poll_interval,
                status_callback=status_updater,
            )
        except TimeoutError as exc:
            self._append_log(job, stage="timed_out", message=str(exc))
            self._append_log(job, stage="fallback", message="tentando fallback por descoberta de artefato...")
            final_reference = await self._find_ready_artifact_fallback(notebook_id, "video")
            if not final_reference:
                self._update_job(job, status=JobStatus.timed_out, error=str(exc))
                raise
            self._append_log(job, stage="fallback", message=f"fallback funcionou: artefato {final_reference} encontrado")

        self._append_log(job, stage="download_video", message="baixando artefato de video...")
        
        import re
        artifact_title = await self._get_artifact_title(notebook_id, final_reference)
        safe_title = re.sub(r'[^a-zA-Z0-9_\-]', '_', artifact_title) if artifact_title else job.id
        artifact_path = self._artifact_service.build_path(safe_title, ".mp4")
        
        downloaded_path = await self._download_with_retry(
            notebook_id=notebook_id,
            artifact_reference=final_reference,
            destination_path=artifact_path,
            media_type="video",
        )
        metadata = self._artifact_service.build_metadata(downloaded_path, content_type="video/mp4")
        if artifact_title:
            metadata.title = artifact_title
        self._notebook_catalog.increment_artifact_count(notebook_id)

        self._append_log(job, stage="download_video", message="artefato de video disponivel")
        self._complete_job(
            job,
            notebook_id=notebook_id,
            artifact_path=_relative_to_data_dir(self._settings.data_dir, downloaded_path),
            artifact_metadata=metadata,
            result={"artifact_reference": final_reference, "media_type": "video/mp4"},
            error=None,
        )

    def _persist_temp_payload(self, temp_dir: Path, payload: JobRequest) -> None:
        file_path = temp_dir / "input.json"
        file_path.write_text(
            json.dumps(payload.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _complete_job(self, job: JobRecord, **changes: Any) -> None:
        self._update_job(
            job,
            status=JobStatus.completed,
            completed_at=_utc_now(),
            **changes,
        )
        self._apply_duration(job)

    def _apply_duration(self, job: JobRecord) -> None:
        if job.started_at is None or job.completed_at is None:
            return
        duration_ms = int((job.completed_at - job.started_at).total_seconds() * 1000)
        self._update_job(job, duration_ms=duration_ms)

    def _append_log(self, job: JobRecord, stage: str, message: str) -> None:
        logs = list(job.logs)
        logs.append(JobLogEntry(at=_utc_now(), stage=stage, message=message))
        self._update_job(job, logs=logs)

    def _update_job(self, job: JobRecord, **changes: Any) -> None:
        for field_name, field_value in changes.items():
            setattr(job, field_name, field_value)
        job.updated_at = _utc_now()
        self._repository.save(job)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _relative_to_data_dir(data_dir: Path, path: Path) -> str:
    try:
        return path.relative_to(data_dir).as_posix()
    except ValueError:
        return path.as_posix()
