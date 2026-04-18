from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.notebooklm_service import NotebookLMPyService, NotebookLMOperationError
from app.services.storage_state_service import StorageStateService

import asyncio

def test_download_artifact_fails_if_file_empty(tmp_path: Path) -> None:
    async def run_test():
        storage_state_path = tmp_path / "storage_state.json"
        storage_state_path.write_text("{}")
        storage_state_service = StorageStateService(storage_state_path=storage_state_path)
        
        service = NotebookLMPyService(storage_state_service=storage_state_service)
        
        # Mock the client
        mock_client = MagicMock()
        mock_client.artifacts.download_audio = AsyncMock()
        mock_client.artifacts.download_video = AsyncMock()
        
        # Mock _get_client
        service._get_client = AsyncMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_client)))
        
        dest = tmp_path / "test.wav"
        
        # Case 1: File doesn't exist
        with pytest.raises(NotebookLMOperationError, match="Falha silenciosa"):
            await service.download_artifact("nb1", "art1", dest)
            
        # Case 2: File is empty
        dest.write_bytes(b"")
        with pytest.raises(NotebookLMOperationError, match="tamanho 0 bytes"):
            await service.download_artifact("nb1", "art1", dest)
        assert not dest.exists() # Should have been unlinked

        # Case 3: Success
        dest.write_bytes(b"some data")
        result = await service.download_artifact("nb1", "art1", dest)
        assert result == dest
        assert dest.exists()

    asyncio.run(run_test())
