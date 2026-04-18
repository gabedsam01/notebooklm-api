import asyncio
from notebooklm import NotebookLMClient

async def main():
    try:
        c = await NotebookLMClient.from_storage('dummy.json')
    except Exception as e:
        print("Error:", e)
        # Even if it errors out, let's see what's in the module
    print("Methods in NotebookLMClient:", [m for m in dir(NotebookLMClient) if not m.startswith('_')])

asyncio.run(main())
