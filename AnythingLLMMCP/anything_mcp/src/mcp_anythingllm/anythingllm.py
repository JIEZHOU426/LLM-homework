"""AnythingLLM REST 客户端。

只做一件事：把 AnythingLLM 的 HTTP 接口包成"要么返回数据、要么抛出结构化
ToolError"的异步方法，让 MCP 工具层不必关心 httpx 细节。

错误码与宠物医院 MCP 保持一致（CONFIG_ERROR / UPSTREAM_* / VALIDATION_ERROR），
失败时**不整段透传**上游响应体。
"""

from __future__ import annotations

import json
import re
from typing import Any

import httpx
from mcp.server.mcpserver.exceptions import ToolError

from .config import settings

CONFIG_ERROR = "CONFIG_ERROR"
VALIDATION_ERROR = "VALIDATION_ERROR"
AUTH_FAILED = "AUTH_FAILED"
UPSTREAM_UNREACHABLE = "UPSTREAM_UNREACHABLE"
UPSTREAM_TIMEOUT = "UPSTREAM_TIMEOUT"
UPSTREAM_HTTP_ERROR = "UPSTREAM_HTTP_ERROR"
UPSTREAM_BAD_PAYLOAD = "UPSTREAM_BAD_PAYLOAD"

_SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_DETAIL_MAX = 160


def tool_error(
    code: str,
    message: str,
    *,
    status: int | None = None,
    detail: str | None = None,
) -> ToolError:
    payload: dict[str, Any] = {"code": code, "message": message}
    if status is not None:
        payload["status"] = status
    if detail:
        payload["detail"] = detail
    return ToolError(json.dumps(payload, ensure_ascii=False))


def require_api_key() -> None:
    """缺 Key 时立刻报错，而不是让请求去撞一个 401。"""

    if not settings.api_key:
        raise tool_error(
            CONFIG_ERROR,
            "缺少 ANYTHINGLLM_API_KEY。请在 anything_mcp/.env 或环境变量中配置"
            "（AnythingLLM → Settings → API Keys 生成）。",
        )


def check_slug(slug: str) -> str:
    """工作区标识会直接拼进 URL，必须先做白名单校验。"""

    slug = (slug or "").strip()
    if not _SLUG_RE.match(slug):
        raise tool_error(
            VALIDATION_ERROR,
            f"工作区标识不合法：{slug!r}。只允许字母、数字、点、下划线、连字符，"
            "且以字母或数字开头（形如 my-workspace）。",
        )
    return slug


def _detail_of(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        body = None
    if isinstance(body, dict):
        for key in ("error", "message", "msg"):
            value = body.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()[:_DETAIL_MAX]
    text = (response.text or "").strip().replace("\n", " ")
    return text[:_DETAIL_MAX] + ("…" if len(text) > _DETAIL_MAX else "")


class AnythingLLMClient:
    """一次性构造，按需复用连接池。"""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self.base_url = settings.base_url.rstrip("/")
        self._client = client or httpx.AsyncClient(
            base_url=self.base_url, timeout=settings.timeout
        )

    # ---------- 基础设施 ----------

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {settings.api_key}"}

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        require_api_key()
        headers = self.headers
        if "json" in kwargs:  # 表单上传不能带 application/json，否则边界被破坏
            headers = {**headers, "Content-Type": "application/json"}
        try:
            response = await self._client.request(
                method, path, headers=headers, **kwargs
            )
        except httpx.TimeoutException as exc:
            raise tool_error(
                UPSTREAM_TIMEOUT,
                f"AnythingLLM（{self.base_url}）响应超时（{settings.timeout:g} 秒）。",
            ) from exc
        except httpx.RequestError as exc:
            raise tool_error(
                UPSTREAM_UNREACHABLE,
                f"无法连接 AnythingLLM（{self.base_url}）。请确认服务已启动"
                "（默认 http://localhost:3001）以及 ANYTHINGLLM_BASE_URL 配置。",
            ) from exc

        if response.status_code in (401, 403):
            raise tool_error(
                AUTH_FAILED,
                "AnythingLLM 拒绝认证，API Key 无效或无该工作区权限。",
                status=response.status_code,
                detail=_detail_of(response),
            )
        if response.is_error:
            raise tool_error(
                UPSTREAM_HTTP_ERROR,
                f"AnythingLLM 接口返回 HTTP {response.status_code}（{method} {path}）。",
                status=response.status_code,
                detail=_detail_of(response),
            )
        return response

    @staticmethod
    def _json(response: httpx.Response) -> dict:
        try:
            body = response.json()
        except ValueError as exc:
            raise tool_error(
                UPSTREAM_BAD_PAYLOAD,
                "AnythingLLM 返回的不是合法 JSON。",
                status=response.status_code,
            ) from exc
        if not isinstance(body, dict):
            raise tool_error(
                UPSTREAM_BAD_PAYLOAD,
                f"AnythingLLM 返回的 JSON 顶层应为对象，实际是 {type(body).__name__}。",
            )
        return body

    # ---------- 业务 ----------

    async def list_workspaces(self) -> dict:
        """列出所有工作区（含 slug、名称、文档数），供模型先挑再聊。"""

        body = self._json(await self._request("GET", "/api/v1/workspaces"))
        workspaces = body.get("workspaces", [])
        if isinstance(workspaces, list) and workspaces and isinstance(workspaces[0], dict):
            # 只保留模型真正需要的字段，避免整段 metadata 灌进上下文
            slim = [
                {
                    key: item.get(key)
                    for key in ("id", "name", "slug", "chatMode", "openAiTemp")
                    if key in item
                }
                for item in workspaces
            ]
            return {"workspaces": slim, "total": len(slim)}
        return {"workspaces": workspaces}

    async def chat(self, slug: str, question: str) -> str:
        slug = check_slug(slug)
        question = (question or "").strip()
        if not question:
            raise tool_error(VALIDATION_ERROR, "question 不能为空。")
        payload = {
            "model": slug,  # AnythingLLM 用 model 字段承载工作区 slug
            "messages": [{"role": "user", "content": question}],
        }
        body = self._json(
            await self._request(
                "POST", "/api/v1/openai/chat/completions", json=payload
            )
        )
        try:
            return body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise tool_error(
                UPSTREAM_BAD_PAYLOAD,
                "AnythingLLM 聊天响应缺少 choices[0].message.content。",
                detail=str(body)[:_DETAIL_MAX],
            ) from exc

    async def upload_and_embed_document(
        self, slug: str, filename: str, content: str
    ) -> dict:
        """上传一份文本文件到工作区并立刻向量化（两步：upload → update-embeddings）。

        没有向量化就不算"进了知识库"，所以这两步合成一个工具，避免模型只做
        上传而忘记 embed。
        """

        slug = check_slug(slug)
        filename = (filename or "").strip()
        if not filename:
            raise tool_error(VALIDATION_ERROR, "filename 不能为空。")
        if any(sep in filename for sep in ("/", "\\", "..")):
            raise tool_error(
                VALIDATION_ERROR,
                f"filename 只能是文件名，不能包含路径：{filename!r}。",
            )
        if not (content or "").strip():
            raise tool_error(VALIDATION_ERROR, "content 不能为空。")

        require_api_key()
        files = {"file": (filename, content.encode("utf-8"), "text/plain")}
        upload = self._json(
            await self._request("POST", "/api/v1/document/upload", files=files)
        )
        documents = upload.get("documents") or []
        if not documents and isinstance(upload.get("document"), dict):
            documents = [upload["document"]]
        if not documents:
            raise tool_error(
                UPSTREAM_BAD_PAYLOAD,
                "上传成功但响应里没有 documents 字段，无法确认文件位置。",
                detail=str(upload)[:_DETAIL_MAX],
            )

        locations = [
            doc.get("location")
            for doc in documents
            if isinstance(doc, dict) and doc.get("location")
        ]
        embed = self._json(
            await self._request(
                "POST",
                f"/api/v1/workspace/{slug}/update-embeddings",
                json={"adds": locations, "deletes": []},
            )
        )
        return {
            "workspace": slug,
            "documents": documents,
            "embedded": bool(embed.get("success", True)),
            "message": embed.get("message", "已提交向量化"),
        }

    async def vector_search(
        self,
        slug: str,
        query: str,
        top_n: int = 5,
        score_threshold: float | None = None,
    ) -> dict:
        """语义检索：返回命中的片段与相似度，不发问、不生成回答。"""

        slug = check_slug(slug)
        query = (query or "").strip()
        if not query:
            raise tool_error(VALIDATION_ERROR, "query 不能为空。")
        if not 1 <= top_n <= 20:
            raise tool_error(VALIDATION_ERROR, "topN 需在 1-20 之间。")
        payload: dict[str, Any] = {"query": query, "topN": top_n}
        if score_threshold is not None:
            if not 0 <= score_threshold <= 1:
                raise tool_error(VALIDATION_ERROR, "scoreThreshold 需在 0-1 之间。")
            payload["scoreThreshold"] = score_threshold

        body = self._json(
            await self._request(
                "POST", f"/api/v1/workspace/{slug}/vector-search", json=payload
            )
        )
        results = body.get("results", [])
        return {
            "workspace": slug,
            "query": query,
            "results": results,
            "total": len(results) if isinstance(results, list) else 0,
        }

    async def close(self) -> None:
        await self._client.aclose()
