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
        self._client: Any = None

    async def verify_access(self) -> NotebookAccessCheck:
        if not self._storage_state_service.exists():
            return NotebookAccessCheck(
                ok=False,
                detail="Storage state ausente. Salve cookies em /auth/storage-state.",
            )

        try:
            await self._invoke(
                method_names=("list_notebooks", "get_notebooks", "list"),
                call_variants=(((), {}),),
            )
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
        result = await self._invoke(
            method_names=("list_notebooks", "get_notebooks", "list"),
            call_variants=(((), {}),),
        )
        if result is None:
            return []
        if isinstance(result, list):
            parsed: list[dict[str, Any]] = []
            for item in result:
                if isinstance(item, dict):
                    parsed.append(item)
                else:
                    parsed.append(
                        {
                            "id": _extract_identifier(item, keys=("id", "notebook_id", "notebookId")),
                            "title": getattr(item, "title", "Notebook"),
                            "source_count": int(getattr(item, "source_count", 0)),
                        }
                    )
            return parsed
        return []

    async def create_notebook(self, title: str) -> str:
        result = await self._invoke(
            method_names=("create_notebook", "createNotebook", "notebook_create"),
            call_variants=(
                ((title,), {}),
                ((), {"title": title}),
            ),
        )
        notebook_id = _extract_identifier(result, keys=("id", "notebook_id", "notebookId"))
        if not notebook_id:
            raise NotebookLMOperationError("Nao foi possivel obter notebook_id")
        return notebook_id

    async def get_notebook(self, notebook_id: str) -> dict[str, Any] | None:
        result = await self._invoke(
            method_names=("get_notebook", "getNotebook", "notebook_get"),
            call_variants=(
                ((), {"notebook_id": notebook_id}),
                ((notebook_id,), {}),
            ),
        )
        if result is None:
            return None
        if isinstance(result, dict):
            return result
        return {
            "id": _extract_identifier(result, keys=("id", "notebook_id", "notebookId")) or notebook_id,
            "title": getattr(result, "title", "Notebook"),
            "source_count": int(getattr(result, "source_count", 0)),
        }

    async def delete_notebook(self, notebook_id: str) -> None:
        await self._invoke(
            method_names=("delete_notebook", "deleteNotebook", "remove_notebook"),
            call_variants=(
                ((), {"notebook_id": notebook_id}),
                ((notebook_id,), {}),
            ),
        )

    async def add_text_source(self, notebook_id: str, title: str, content: str) -> str | None:
        result = await self._invoke(
            method_names=(
                "add_text_source",
                "add_source_from_text",
                "upload_text_source",
                "addTextSource",
            ),
            call_variants=(
                ((), {"notebook_id": notebook_id, "title": title, "content": content}),
                ((), {"notebook_id": notebook_id, "source_title": title, "text": content}),
                ((notebook_id, title, content), {}),
            ),
        )
        return _extract_identifier(result, keys=("id", "source_id", "sourceId"))

    async def add_text_sources_batch(
        self,
        notebook_id: str,
        sources: list[dict[str, str]],
    ) -> list[str]:
        source_ids: list[str] = []
        for source in sources:
            source_id = await self.add_text_source(notebook_id, source["title"], source["content"])
            if source_id:
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
        result = await self._invoke(
            method_names=(
                "generate_audio_summary",
                "generate_audio",
                "generate_podcast",
                "create_audio_overview",
            ),
            call_variants=(
                (
                    (),
                    {
                        "notebook_id": notebook_id,
                        "mode": mode,
                        "language": language,
                        "duration": duration,
                        "focus_prompt": focus_prompt,
                    },
                ),
                ((notebook_id, focus_prompt), {}),
            ),
        )
        artifact_id = _extract_identifier(
            result,
            keys=("id", "artifact_id", "audio_id", "job_id", "task_id"),
        )
        if not artifact_id:
            raise NotebookLMOperationError("Nao foi possivel obter referencia do artefato de audio")
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
        result = await self._invoke(
            method_names=(
                "generate_video_summary",
                "generate_video",
                "create_video_overview",
            ),
            call_variants=(
                (
                    (),
                    {
                        "notebook_id": notebook_id,
                        "mode": mode,
                        "style": style,
                        "language": language,
                        "visual_style": visual_style,
                        "focus_prompt": focus_prompt,
                    },
                ),
                ((notebook_id, focus_prompt), {}),
            ),
        )
        artifact_id = _extract_identifier(
            result,
            keys=("id", "artifact_id", "video_id", "job_id", "task_id"),
        )
        if not artifact_id:
            raise NotebookLMOperationError("Nao foi possivel obter referencia do artefato de video")
        return artifact_id

    async def wait_for_artifact(
        self,
        notebook_id: str,
        artifact_reference: str,
        timeout_seconds: int,
        poll_interval_seconds: float,
    ) -> str:
        try:
            result = await self._invoke(
                method_names=(
                    "wait_for_artifact",
                    "wait_for_audio",
                    "wait_for_video",
                    "wait_for_generation",
                ),
                call_variants=(
                    (
                        (),
                        {
                            "notebook_id": notebook_id,
                            "artifact_id": artifact_reference,
                            "timeout": timeout_seconds,
                            "poll_interval": poll_interval_seconds,
                        },
                    ),
                    ((notebook_id, artifact_reference), {}),
                ),
            )
            resolved = _extract_identifier(
                result,
                keys=("id", "artifact_id", "audio_id", "video_id", "job_id", "task_id"),
            )
            return resolved or artifact_reference
        except NotebookLMOperationError:
            return artifact_reference

    async def download_artifact(
        self,
        notebook_id: str,
        artifact_reference: str,
        destination_path: Path,
    ) -> Path:
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        result = await self._invoke(
            method_names=(
                "download_artifact",
                "download_audio",
                "download_video",
                "download",
            ),
            call_variants=(
                (
                    (),
                    {
                        "notebook_id": notebook_id,
                        "artifact_id": artifact_reference,
                        "destination": str(destination_path),
                    },
                ),
                ((notebook_id, artifact_reference, str(destination_path)), {}),
                ((notebook_id, artifact_reference), {}),
            ),
        )

        if isinstance(result, bytes):
            destination_path.write_bytes(result)
            return destination_path

        if isinstance(result, str | Path):
            result_path = Path(result)
            if result_path.exists():
                if result_path.resolve() != destination_path.resolve():
                    shutil.copyfile(result_path, destination_path)
                return destination_path

        if destination_path.exists():
            return destination_path

        raise NotebookLMOperationError("NotebookLM nao retornou arquivo para download")

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client

        if not self._storage_state_service.exists():
            raise NotebookLMOperationError("storage_state nao encontrado")

        module = None
        for module_name in ("notebooklm_py", "notebooklm"):
            try:
                module = importlib.import_module(module_name)
                break
            except ModuleNotFoundError:
                continue

        if module is None:
            raise NotebookLMOperationError(
                "Biblioteca notebooklm-py nao encontrada. Configure NOTEBOOKLM_MODE=mock ou instale a lib."
            )

        client_class = None
        for class_name in ("NotebookLMClient", "Client", "NotebookLM"):
            candidate = getattr(module, class_name, None)
            if candidate is not None:
                client_class = candidate
                break

        if client_class is None:
            raise NotebookLMOperationError("Classe cliente do notebooklm-py nao encontrada")

        storage_path = str(self._storage_state_service.storage_state_path)
        init_variants = (
            ((), {"storage_state_path": storage_path}),
            ((), {"storage_state": storage_path}),
            ((), {"cookies_path": storage_path}),
            ((storage_path,), {}),
            ((), {}),
        )

        last_error: Exception | None = None
        for args, kwargs in init_variants:
            try:
                instance = client_class(*args, **kwargs)
                self._client = instance
                return instance
            except TypeError as exc:
                last_error = exc
                continue
            except Exception as exc:  # noqa: BLE001
                raise NotebookLMOperationError("Falha ao inicializar cliente notebooklm-py") from exc

        raise NotebookLMOperationError("Nao foi possivel inicializar notebooklm-py") from last_error

    async def _invoke(
        self,
        method_names: Sequence[str],
        call_variants: Sequence[tuple[tuple[Any, ...], dict[str, Any]]],
    ) -> Any:
        client = self._get_client()

        for method_name in method_names:
            method = getattr(client, method_name, None)
            if not callable(method):
                continue

            last_type_error: TypeError | None = None
            for args, kwargs in call_variants:
                try:
                    result = method(*args, **kwargs)
                    if inspect.isawaitable(result):
                        return await result
                    return result
                except TypeError as exc:
                    last_type_error = exc
                    continue

            if last_type_error is not None:
                raise NotebookLMOperationError(
                    f"Metodo '{method_name}' nao aceitou assinatura esperada"
                ) from last_type_error

        raise NotebookLMOperationError(
            f"Metodo notebooklm-py nao encontrado. Esperado: {', '.join(method_names)}"
        )


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
