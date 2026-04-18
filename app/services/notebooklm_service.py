from __future__ import annotations

import asyncio
import importlib
import inspect
import io
import math
import shutil
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, Sequence
from uuid import uuid4

from app.core.config import Settings
from app.services.storage_state_service import StorageStateService
from app.utils.error_sanitizer import sanitize_exception


class NotebookLMOperationError(RuntimeError):
    """Raised when NotebookLM operations cannot be completed."""


@dataclass(slots=True)
class NotebookAccessCheck:
    ok: bool
    detail: str


class NotebookLMService(Protocol):
    async def verify_access(self) -> NotebookAccessCheck:
        ...

    async def list_notebooks(self) -> list[dict[str, Any]]:
        ...

    async def create_notebook(self, title: str) -> str:
        ...

    async def get_notebook(self, notebook_id: str) -> dict[str, Any] | None:
        ...

    async def delete_notebook(self, notebook_id: str) -> None:
        ...

    async def add_text_source(self, notebook_id: str, title: str, content: str) -> str | None:
        ...

    async def add_text_sources_batch(
        self,
        notebook_id: str,
        sources: list[dict[str, str]],
    ) -> list[str]:
        ...

    async def generate_audio_summary(
        self,
        notebook_id: str,
        mode: str,
        language: str,
        duration: str,
        focus_prompt: str,
    ) -> str:
        ...

    async def generate_video_summary(
        self,
        notebook_id: str,
        mode: str,
        style: str,
        language: str,
        visual_style: str | None,
        focus_prompt: str,
    ) -> str:
        ...

    async def wait_for_artifact(
        self,
        notebook_id: str,
        artifact_reference: str,
        timeout_seconds: int,
        poll_interval_seconds: float,
    ) -> str:
        ...

    async def download_artifact(
        self,
        notebook_id: str,
        artifact_reference: str,
        destination_path: Path,
    ) -> Path:
        ...


class MockNotebookLMService:
    """In-memory fake used for tests and local development."""

    def __init__(self, storage_state_service: StorageStateService) -> None:
        self._storage_state_service = storage_state_service
        self._notebooks: dict[str, dict[str, Any]] = {}
        self._artifacts: dict[str, dict[str, Any]] = {}

    async def verify_access(self) -> NotebookAccessCheck:
        if not self._storage_state_service.exists():
            return NotebookAccessCheck(
                ok=False,
                detail="Storage state ausente. Salve cookies em /auth/storage-state.",
            )
        return NotebookAccessCheck(ok=True, detail="Acesso validado em modo mock.")

    async def list_notebooks(self) -> list[dict[str, Any]]:
        return [
            {
                "id": notebook_id,
                "title": notebook["title"],
                "source_count": len(notebook["sources"]),
            }
            for notebook_id, notebook in self._notebooks.items()
        ]

    async def create_notebook(self, title: str) -> str:
        notebook_id = f"mock-nb-{uuid4().hex}"
        self._notebooks[notebook_id] = {"id": notebook_id, "title": title, "sources": []}
        return notebook_id

    async def get_notebook(self, notebook_id: str) -> dict[str, Any] | None:
        notebook = self._notebooks.get(notebook_id)
        if notebook is None:
            return None
        return {
            "id": notebook["id"],
            "title": notebook["title"],
            "source_count": len(notebook["sources"]),
        }

    async def delete_notebook(self, notebook_id: str) -> None:
        self._notebooks.pop(notebook_id, None)

    async def add_text_source(self, notebook_id: str, title: str, content: str) -> str:
        notebook = self._notebooks.get(notebook_id)
        if notebook is None:
            raise NotebookLMOperationError("Notebook nao encontrado")
        source_id = f"src-{uuid4().hex}"
        notebook["sources"].append({"id": source_id, "title": title, "content": content})
        return source_id

    async def add_text_sources_batch(
        self,
        notebook_id: str,
        sources: list[dict[str, str]],
    ) -> list[str]:
        source_ids: list[str] = []
        for source in sources:
            source_id = await self.add_text_source(
                notebook_id=notebook_id,
                title=source["title"],
                content=source["content"],
            )
            source_ids.append(source_id)
        return source_ids

    async def generate_audio_summary(
        self,
        notebook_id: str,
        mode: str,
        language: str,
        duration: str,
        focus_prompt: str,
    ) -> str:
        _ = mode
        _ = language
        _ = duration
        _ = focus_prompt
        notebook = self._notebooks.get(notebook_id)
        if notebook is None:
            raise NotebookLMOperationError("Notebook nao encontrado para gerar audio")
        if not notebook["sources"]:
            raise NotebookLMOperationError("Notebook sem fontes para gerar audio")

        artifact_id = f"audio-{uuid4().hex}"
        self._artifacts[artifact_id] = {
            "notebook_id": notebook_id,
            "media_type": "audio/wav",
            "bytes": _build_mock_wav(),
        }
        return artifact_id

    async def generate_video_summary(
        self,
        notebook_id: str,
        mode: str,
        style: str,
        language: str,
        visual_style: str | None,
        focus_prompt: str,
    ) -> str:
        _ = mode
        _ = style
        _ = language
        _ = visual_style
        _ = focus_prompt
        notebook = self._notebooks.get(notebook_id)
        if notebook is None:
            raise NotebookLMOperationError("Notebook nao encontrado para gerar video")
        if not notebook["sources"]:
            raise NotebookLMOperationError("Notebook sem fontes para gerar video")

        artifact_id = f"video-{uuid4().hex}"
        self._artifacts[artifact_id] = {
            "notebook_id": notebook_id,
            "media_type": "video/mp4",
            "bytes": _build_mock_mp4(),
        }
        return artifact_id

    async def wait_for_artifact(
        self,
        notebook_id: str,
        artifact_reference: str,
        timeout_seconds: int,
        poll_interval_seconds: float,
    ) -> str:
        _ = notebook_id
        _ = timeout_seconds
        _ = poll_interval_seconds
        if artifact_reference not in self._artifacts:
            raise NotebookLMOperationError("Artefato nao encontrado")
        await asyncio.sleep(0.05)
        return artifact_reference

    async def download_artifact(
        self,
        notebook_id: str,
        artifact_reference: str,
        destination_path: Path,
    ) -> Path:
        artifact = self._artifacts.get(artifact_reference)
        if artifact is None:
            raise NotebookLMOperationError("Artefato nao encontrado para download")
        if artifact["notebook_id"] != notebook_id:
            raise NotebookLMOperationError("Artefato nao pertence ao notebook informado")

        destination_path.parent.mkdir(parents=True, exist_ok=True)
        destination_path.write_bytes(artifact["bytes"])
        return destination_path


class NotebookLMPyService:
    """Defensive adapter for notebooklm-py (unofficial API)."""

    def __init__(self, storage_state_service: StorageStateService) -> None:
        self._storage_state_service = storage_state_service

    async def _get_client(self) -> "NotebookLMClient":
        from notebooklm import NotebookLMClient
        if not self._storage_state_service.exists():
            raise NotebookLMOperationError("Storage state ausente. Salve cookies em /auth/storage-state.")
        
        try:
            return await NotebookLMClient.from_storage(str(self._storage_state_service.storage_state_path))
        except Exception as exc:
            raise NotebookLMOperationError(f"Falha ao inicializar cliente: {sanitize_exception(exc)}") from exc

    async def verify_access(self) -> NotebookAccessCheck:
        if not self._storage_state_service.exists():
            return NotebookAccessCheck(
                ok=False,
                detail="Storage state ausente. Salve cookies em /auth/storage-state.",
            )

        try:
            async with await self._get_client() as client:
                await client.notebooks.list()
            return NotebookAccessCheck(ok=True, detail="Sessao NotebookLM validada.")
        except Exception as exc:  # noqa: BLE001
            return NotebookAccessCheck(
                ok=False,
                detail=(
                    "Falha ao validar sessao notebooklm-py "
                    f"({sanitize_exception(exc)})."
                ),
            )

    async def list_notebooks(self) -> list[dict[str, Any]]:
        async with await self._get_client() as client:
            notebooks = await client.notebooks.list()
            return [
                {
                    "id": nb.id,
                    "title": nb.title,
                    "source_count": nb.sources_count,
                }
                for nb in notebooks
            ]

    async def create_notebook(self, title: str) -> str:
        async with await self._get_client() as client:
            notebook = await client.notebooks.create(title)
            return notebook.id

    async def get_notebook(self, notebook_id: str) -> dict[str, Any] | None:
        try:
            from notebooklm.exceptions import NotebookNotFoundError
        except ImportError:
            NotebookNotFoundError = Exception

        async with await self._get_client() as client:
            try:
                notebook = await client.notebooks.get(notebook_id)
                return {
                    "id": notebook.id,
                    "title": notebook.title,
                    "source_count": notebook.sources_count,
                }
            except NotebookNotFoundError:
                return None
            except Exception as e:
                # If the exception is 'not found' by string
                if "not found" in str(e).lower() or "404" in str(e):
                    return None
                raise

    async def delete_notebook(self, notebook_id: str) -> None:
        async with await self._get_client() as client:
            await client.notebooks.delete(notebook_id)

    async def add_text_source(self, notebook_id: str, title: str, content: str) -> str | None:
        async with await self._get_client() as client:
            source = await client.sources.add_text(notebook_id, title=title, content=content)
            return source.id

    async def add_text_sources_batch(
        self,
        notebook_id: str,
        sources: list[dict[str, str]],
    ) -> list[str]:
        source_ids: list[str] = []
        async with await self._get_client() as client:
            for source in sources:
                src = await client.sources.add_text(notebook_id, title=source["title"], content=source["content"])
                source_ids.append(src.id)
        return source_ids

    async def generate_audio_summary(
        self,
        notebook_id: str,
        mode: str,
        language: str,
        duration: str,
        focus_prompt: str,
    ) -> str:
        async with await self._get_client() as client:
            # We can map parameters, but for now we just pass language and instructions
            status = await client.artifacts.generate_audio(
                notebook_id=notebook_id,
                language=language,
                instructions=focus_prompt if focus_prompt else None,
            )
            return status.task_id

    async def generate_video_summary(
        self,
        notebook_id: str,
        mode: str,
        style: str,
        language: str,
        visual_style: str | None,
        focus_prompt: str,
    ) -> str:
        async with await self._get_client() as client:
            status = await client.artifacts.generate_video(
                notebook_id=notebook_id,
                language=language,
                instructions=focus_prompt if focus_prompt else None,
            )
            return status.task_id

    async def wait_for_artifact(
        self,
        notebook_id: str,
        artifact_reference: str,
        timeout_seconds: int,
        poll_interval_seconds: float,
    ) -> str:
        async with await self._get_client() as client:
            # Task ID is our artifact reference for Audio/Video
            status = await client.artifacts.wait_for_completion(
                notebook_id=notebook_id,
                task_id=artifact_reference,
                timeout=float(timeout_seconds),
                initial_interval=poll_interval_seconds,
            )
            # The downloaded audio/video uses task_id (or status.task_id) implicitly if artifact_id is None,
            # but wait_for_completion returns a status where task_id is usually the artifact_id for completed audio.
            return status.task_id or artifact_reference

    async def download_artifact(
        self,
        notebook_id: str,
        artifact_reference: str,
        destination_path: Path,
    ) -> Path:
        async with await self._get_client() as client:
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Since we generated audio/video and have a task_id/artifact_id
            # Try to guess which one it is or use general download if available
            # Let's try audio first, if it fails, try video. Or just call poll_status to see what it is
            
            try:
                # If artifact_reference looks like a task_id for an audio, we can try downloading audio.
                # Actually, notebooklm-py 0.3 download_audio just gets the latest completed if artifact_id is None.
                # If we pass artifact_id=artifact_reference, it filters. Let's try downloading audio first.
                await client.artifacts.download_audio(
                    notebook_id=notebook_id, 
                    output_path=str(destination_path),
                    artifact_id=artifact_reference
                )
                return destination_path
            except Exception as e_audio:
                try:
                    await client.artifacts.download_video(
                        notebook_id=notebook_id, 
                        output_path=str(destination_path),
                        artifact_id=artifact_reference
                    )
                    return destination_path
                except Exception as e_video:
                    raise NotebookLMOperationError(f"Falha ao baixar artefato: Audio({e_audio}), Video({e_video})")


def build_notebook_service(
    settings: Settings,
    storage_state_service: StorageStateService,
) -> NotebookLMService:
    if settings.notebooklm_mode == "real":
        return NotebookLMPyService(storage_state_service=storage_state_service)
    return MockNotebookLMService(storage_state_service=storage_state_service)


def _extract_identifier(result: Any, keys: Sequence[str]) -> str | None:
    if result is None:
        return None
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        for key in keys:
            value = result.get(key)
            if value is not None:
                return str(value)
    for key in keys:
        value = getattr(result, key, None)
        if value is not None:
            return str(value)
    return None


def _build_mock_wav() -> bytes:
    sample_rate = 22_050
    duration_seconds = 1.2
    frequency_hz = 220.0
    total_frames = int(sample_rate * duration_seconds)

    with io.BytesIO() as buffer:
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            frames = bytearray()
            for index in range(total_frames):
                t = index / sample_rate
                amplitude = int(16_000 * math.sin(2.0 * math.pi * frequency_hz * t))
                frames.extend(amplitude.to_bytes(2, byteorder="little", signed=True))
            wav_file.writeframes(bytes(frames))
        return buffer.getvalue()


def _build_mock_mp4() -> bytes:
    # Minimal byte sequence with MP4-like signature for integration tests.
    return b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom\x00\x00\x00\x08free"
