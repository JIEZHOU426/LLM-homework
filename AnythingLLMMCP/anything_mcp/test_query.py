import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import httpx

from mcp_anythingllm.config import settings


async def main():
    url = settings.base_url.rstrip("/") + "/api/v1/openai/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "46decf1f-7fe5-4d03-9584-9d2b6f2743a0",
        "messages": [{"role": "user", "content": "草坪上有什么"}],
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload, headers=headers)
        data = resp.json()
        print(data["choices"][0]["message"]["content"])


asyncio.run(main())
