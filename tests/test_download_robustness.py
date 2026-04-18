"""Tests de robustez para download de artefatos e retry com backoff."""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.notebooklm_service import NotebookLMPyService, NotebookLMOperationError, MockNotebookLMService
from app.services.storage_state_service import StorageStateService


# ==========================================================================
# Tests: Download tipado (media_type="audio" | "video")
# ==========================================================================

def test_download_artifact_calls_download_audio_for_audio_type(tmp_path: Path) -> None:
    """download_artifact com media_type='audio' deve chamar download_audio da lib."""
    async def run():
        storage_state_path = tmp_path / "storage_state.json"
        storage_state_path.write_text("{}")
        service = NotebookLMPyService(
            storage_state_service=StorageStateService(storage_state_path=storage_state_path),
        )

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
    """download_artifact com media_type='video' deve chamar download_video da lib."""
    async def run():
        storage_state_path = tmp_path / "storage_state.json"
        storage_state_path.write_text("{}")
        service = NotebookLMPyService(
            storage_state_service=StorageStateService(storage_state_path=storage_state_path),
        )

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


# ==========================================================================
# Tests: Robustez — arquivo vazio ou inexistente
# ==========================================================================

def test_download_artifact_fails_if_file_empty(tmp_path: Path) -> None:
    async def run_test():
        storage_state_path = tmp_path / "storage_state.json"
        storage_state_path.write_text("{}")
        storage_state_service = StorageStateService(storage_state_path=storage_state_path)

        service = NotebookLMPyService(storage_state_service=storage_state_service)

        mock_client = MagicMock()
        mock_client.artifacts.download_audio = AsyncMock()
        mock_client.artifacts.download_video = AsyncMock()

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        service._get_client = AsyncMock(return_value=mock_ctx)

        dest = tmp_path / "test.wav"

        # Case 1: File doesn't exist after download
        with pytest.raises(NotebookLMOperationError, match="Falha silenciosa"):
            await service.download_artifact("nb1", "art1", dest, media_type="audio")

        # Case 2: File is empty (0 bytes)
        dest.write_bytes(b"")
        with pytest.raises(NotebookLMOperationError, match="0 bytes"):
            await service.download_artifact("nb1", "art1", dest, media_type="audio")
        assert not dest.exists()  # Should have been unlinked

        # Case 3: Success — file has content
        dest.write_bytes(b"some data")
        result = await service.download_artifact("nb1", "art1", dest, media_type="audio")
        assert result == dest
        assert dest.exists()

    asyncio.run(run_test())


# ==========================================================================
# Tests: Retry com backoff exponencial (via JobService._download_with_retry)
# ==========================================================================

def test_download_with_retry_succeeds_on_third_attempt(tmp_path: Path) -> None:
    """Retry deve ter sucesso se a terceira tentativa funcionar."""
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
        job_service._notebook_service = mock_service

        result = await job_service._download_with_retry(
            notebook_id="nb1",
            artifact_reference="art1",
            destination_path=dest,
            media_type="audio",
            max_attempts=3,
            base_delay=0.01,  # rápido para testes
        )

        assert result == dest
        assert call_count == 3

    asyncio.run(run())


def test_download_with_retry_fails_after_max_attempts(tmp_path: Path) -> None:
    """Retry deve lançar erro após esgotar tentativas."""
    from app.services.job_service import JobService

    async def run():
        dest = tmp_path / "test.wav"

        mock_service = MagicMock()
        mock_service.download_artifact = AsyncMock(
            side_effect=NotebookLMOperationError("Falha permanente"),
        )

        job_service = JobService.__new__(JobService)
        job_service._notebook_service = mock_service

        with pytest.raises(NotebookLMOperationError, match="Falha permanente"):
            await job_service._download_with_retry(
                notebook_id="nb1",
                artifact_reference="art1",
                destination_path=dest,
                media_type="audio",
                max_attempts=3,
                base_delay=0.01,
            )

        assert mock_service.download_artifact.call_count == 3

    asyncio.run(run())


def test_download_with_retry_succeeds_on_first_attempt(tmp_path: Path) -> None:
    """Se o primeiro download funcionar, não deve haver retry."""
    from app.services.job_service import JobService

    async def run():
        dest = tmp_path / "test.wav"

        async def ok_download(notebook_id, artifact_reference, destination_path, media_type="audio"):
            destination_path.write_bytes(b"audio data")
            return destination_path

        mock_service = MagicMock()
        mock_service.download_artifact = AsyncMock(side_effect=ok_download)

        job_service = JobService.__new__(JobService)
        job_service._notebook_service = mock_service

        result = await job_service._download_with_retry(
            notebook_id="nb1",
            artifact_reference="art1",
            destination_path=dest,
            media_type="audio",
            max_attempts=3,
            base_delay=0.01,
        )

        assert result == dest
        assert mock_service.download_artifact.call_count == 1

    asyncio.run(run())


# ==========================================================================
# Tests: MockNotebookLMService aceita media_type
# ==========================================================================

def test_mock_service_download_accepts_media_type(tmp_path: Path) -> None:
    """MockNotebookLMService.download_artifact deve aceitar media_type sem erro."""
    async def run():
        storage_state_path = tmp_path / "storage_state.json"
        storage_state_path.write_text("{}")
        service = MockNotebookLMService(
            storage_state_service=StorageStateService(storage_state_path=storage_state_path),
        )

        # Setup: create notebook and generate audio
        nb_id = await service.create_notebook("test")
        await service.add_text_source(nb_id, "src", "content")
        art_ref = await service.generate_audio_summary(nb_id, "summary", "pt-BR", "standard", "prompt")

        dest = tmp_path / "output.wav"

        # Should work with explicit media_type
        result = await service.download_artifact(nb_id, art_ref, dest, media_type="audio")
        assert result == dest
        assert dest.exists()

    asyncio.run(run())
