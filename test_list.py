import asyncio
from notebooklm import NotebookLMClient
from app.services.storage_state_service import StorageStateService
from app.core.config import get_settings

async def main():
    settings = get_settings()
    storage = StorageStateService(settings.storage_state_path)
    async with NotebookLMClient(auth=storage.auth_tokens) as client:
        pass
        # print(dir(client.artifacts))
