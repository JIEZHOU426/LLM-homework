import httpx
from .config import settings


class AnythingLLMClient:
    def __init__(self):
        self.base_url = settings.base_url.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {settings.api_key}",
            "Content-Type": "application/json",
        }
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=30)

    async def list_workspaces(self) -> dict:
        resp = await self._client.get("/api/v1/workspaces", headers=self.headers)
        resp.raise_for_status()
        return resp.json()

    async def chat(self, slug: str, question: str, top_k: int = 5, threshold: float = 0.2) -> str:
        payload = {
            "model": slug,
            "messages": [{"role": "user", "content": question}],
        }
        resp = await self._client.post("/api/v1/openai/chat/completions", json=payload, headers=self.headers)
        resp.raise_for_status()
        result = resp.json()
        return result["choices"][0]["message"]["content"]

    async def close(self):
        await self._client.aclose()
