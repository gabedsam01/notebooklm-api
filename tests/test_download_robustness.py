"""Tests de robustez para download de artefatos e retry com backoff."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.jobs import JobStatus
from app.services.notebooklm_service import NotebookLMPyService, NotebookLMOperationError, MockNotebookLMService
from app.services.storage_state_service import StorageStateService


def test_download_artifact_calls_download_audio_for_audio_type(tmp_path: Path) -> None:
    async def run():
        storage_state_path = tmp_path / "storage_state.json"
        storage_state_path.write_text("{}")
        service = NotebookLMPyService(storage_state_service=StorageStateService(storage_state_path=storage_state_path))

        mock_client = MagicMock()
        mock_client.artifacts.download_audio = AsyncMock()
        mock_client.artifacts.download_video = AsyncMock()

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        service._get_client = AsyncMock(return_value=mock_ctx)

        dest = tmp_path / "test.wav"
        dest.write_bytes(b"fake audio data")

        await service.download_artifact("nb1", "art1", dest, media_type="audio")

        mock_client.artifacts.download_audio.assert_called_once()
        mock_client.artifacts.download_video.assert_not_called()

    asyncio.run(run())


def test_download_artifact_calls_download_video_for_video_type(tmp_path: Path) -> None:
    async def run():
        storage_state_path = tmp_path / "storage_state.json"
        storage_state_path.write_text("{}")
        service = NotebookLMPyService(storage_state_service=StorageStateService(storage_state_path=storage_state_path))

        mock_client = MagicMock()
        mock_client.artifacts.download_audio = AsyncMock()
        mock_client.artifacts.download_video = AsyncMock()

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        service._get_client = AsyncMock(return_value=mock_ctx)

        dest = tmp_path / "test.mp4"
        dest.write_bytes(b"fake video data")

        await service.download_artifact("nb1", "art1", dest, media_type="video")

        mock_client.artifacts.download_video.assert_called_once()
        mock_client.artifacts.download_audio.assert_not_called()

    asyncio.run(run())


def test_download_artifact_sets_notebooklm_home_per_account(tmp_path: Path) -> None:
    async def run():
        storage_state_path = tmp_path / "acc" / "storage_state.json"
        storage_state_path.parent.mkdir(parents=True, exist_ok=True)
        storage_state_path.write_text("{}")
        service = NotebookLMPyService(storage_state_service=StorageStateService(storage_state_path=storage_state_path))

        seen = {"home": None}

        async def fake_audio(**kwargs):
            seen["home"] = os.environ.get("NOTEBOOKLM_HOME")
            Path(kwargs["output_path"]).write_bytes(b"audio data")

        mock_client = MagicMock()
        mock_client.artifacts.download_audio = AsyncMock(side_effect=fake_audio)
        mock_client.artifacts.download_video = AsyncMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        service._get_client = AsyncMock(return_value=mock_ctx)

        dest = tmp_path / "out.wav"
        await service.download_artifact("nb1", "art1", dest, media_type="audio")
        assert seen["home"] == str(storage_state_path.parent)

    asyncio.run(run())


def test_download_artifact_fails_if_file_empty(tmp_path: Path) -> None:
    async def run_test():
        storage_state_path = tmp_path / "storage_state.json"
        storage_state_path.write_text("{}")
        service = NotebookLMPyService(storage_state_service=StorageStateService(storage_state_path=storage_state_path))

        mock_client = MagicMock()
        mock_client.artifacts.download_audio = AsyncMock()
        mock_client.artifacts.download_video = AsyncMock()

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        service._get_client = AsyncMock(return_value=mock_ctx)

        dest = tmp_path / "test.wav"

        with pytest.raises(NotebookLMOperationError, match="Falha silenciosa"):
            await service.download_artifact("nb1", "art1", dest, media_type="audio")

        dest.write_bytes(b"")
        with pytest.raises(NotebookLMOperationError, match="0 bytes"):
            await service.download_artifact("nb1", "art1", dest, media_type="audio")
        assert not dest.exists()

        dest.write_bytes(b"some data")
        result = await service.download_artifact("nb1", "art1", dest, media_type="audio")
        assert result == dest
        assert dest.exists()

    asyncio.run(run_test())


def test_download_with_retry_succeeds_on_third_attempt(tmp_path: Path) -> None:
    from app.services.job_service import JobService

    async def run():
        dest = tmp_path / "test.wav"
        call_count = 0

        async def flaky_download(notebook_id, artifact_reference, destination_path, media_type="audio"):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise NotebookLMOperationError("Artefato não pronto")
            destination_path.write_bytes(b"audio data")
            return destination_path

        mock_service = MagicMock()
        mock_service.download_artifact = AsyncMock(side_effect=flaky_download)

        job_service = JobService.__new__(JobService)

        result = await job_service._download_with_retry(
            mock_service,
            notebook_id="nb1",
            artifact_reference="art1",
            destination_path=dest,
            media_type="audio",
            max_attempts=3,
            base_delay=0.01,
        )

        assert result == dest
        assert call_count == 3

    asyncio.run(run())


def test_download_with_retry_fails_after_max_attempts(tmp_path: Path) -> None:
    from app.services.job_service import JobService

    async def run():
        dest = tmp_path / "test.wav"
        mock_service = MagicMock()
        mock_service.download_artifact = AsyncMock(side_effect=NotebookLMOperationError("Falha permanente"))
        job_service = JobService.__new__(JobService)

        with pytest.raises(NotebookLMOperationError, match="Falha permanente"):
            await job_service._download_with_retry(
                mock_service,
                notebook_id="nb1",
                artifact_reference="art1",
                destination_path=dest,
                media_type="audio",
                max_attempts=3,
                base_delay=0.01,
            )

        assert mock_service.download_artifact.call_count == 3

    asyncio.run(run())


def test_mock_service_download_accepts_media_type(tmp_path: Path) -> None:
    async def run():
        storage_state_path = tmp_path / "storage_state.json"
        storage_state_path.write_text("{}")
        service = MockNotebookLMService(storage_state_service=StorageStateService(storage_state_path=storage_state_path))

        nb_id = await service.create_notebook("test")
        await service.add_text_source(nb_id, "src", "content")
        art_ref = await service.generate_audio_summary(nb_id, "summary", "pt-BR", "standard", "prompt")

        dest = tmp_path / "output.wav"
        result = await service.download_artifact(nb_id, art_ref, dest, media_type="audio")
        assert result == dest
        assert dest.exists()

    asyncio.run(run())
