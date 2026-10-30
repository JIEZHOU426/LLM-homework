import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import httpx

from mcp_anythingllm.config import settings


async def main():
    headers = {
        "Authorization": f"Bearer {settings.api_key}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient() as client:
        endpoints = [
            "/api/v1/workspaces",
            "/api/v1/workspaces/46decf1f-7fe5-4d03-9584-9d2b6f2743a0",
            "/api/v1/app/document/workspace/46decf1f-7fe5-4d03-9584-9d2b6f2743a0",
            "/api/v1/workspace/46decf1f-7fe5-4d03-9584-9d2b6f2743a0",
        ]
        for ep in endpoints:
            try:
                url = settings.base_url.rstrip("/") + ep
                resp = await client.get(url, headers=headers)
                print(f"{ep}: {resp.status_code} - {resp.text[:600]}")
            except Exception as e:
                print(f"{ep}: Error - {e}")


asyncio.run(main())
