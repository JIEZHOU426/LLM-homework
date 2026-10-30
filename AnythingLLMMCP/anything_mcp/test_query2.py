import asyncio
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR / "src"))

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
        answer = data["choices"][0]["message"]["content"]
        (BASE_DIR / "answer.txt").write_text(answer, encoding="utf-8")


asyncio.run(main())
