import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import httpx

from mcp_anythingllm.config import settings


async def main():
    url = settings.base_url.rstrip("/") + "/api/v1/workspaces"
    headers = {
        "Authorization": f"Bearer {settings.api_key}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers)
        data = resp.json()
        ws = data["workspaces"][0]
        print(f"Workspace: {ws['name']} ({ws['slug']})")
        print(f"Thread names: {[t['name'] for t in ws['threads']]}")
        print(f"Thread count: {len(ws['threads'])}")

        ws_id = ws["id"]
        for suffix in ["/documents", "/vectors", "/chunks"]:
            try:
                doc_url = (
                    settings.base_url.rstrip("/")
                    + f"/api/v1/workspaces/{ws_id}{suffix}"
                )
                resp2 = await client.get(doc_url, headers=headers)
                print(f"{suffix}: {resp2.text[:800]}")
            except Exception as e:
                print(f"{suffix}: Error - {e}")


asyncio.run(main())
