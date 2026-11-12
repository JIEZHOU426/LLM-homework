"""AnythingLLM 客户端的错误语义与端点契约。

用 ``httpx.MockTransport`` 拦掉真实网络：既验证"发了什么请求"，也验证
"出错时模型看到什么"。跑法（在 AnythingLLM/anything_mcp 下）：

    python -m unittest discover -s tests -t . -v
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

import httpx

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import mcp_anythingllm.anythingllm as al  # noqa: E402
from mcp_anythingllm.config import settings  # noqa: E402


def error_payload(exc: Exception) -> dict:
    return json.loads(str(exc))


class ClientTest(unittest.TestCase):
    def setUp(self) -> None:
        self.requests: list[httpx.Request] = []
        self._settings = settings

    def tearDown(self) -> None:
        al.settings = self._settings

    def configure(self, handler, api_key: str = "test-key") -> None:
        al.settings = dataclasses.replace(
            settings, api_key=api_key, base_url="http://anythingllm.test"
        )
        transport = httpx.MockTransport(self._record(handler))
        self.client = al.AnythingLLMClient(
            client=httpx.AsyncClient(transport=transport, base_url="http://anythingllm.test")
        )

    def _record(self, handler):
        def wrapped(request: httpx.Request) -> httpx.Response:
            self.requests.append(request)
            return handler(request)

        return wrapped

    def run_async(self, coro):
        return asyncio.run(coro)

    # ---------- 配置与校验 ----------

    def test_missing_api_key_is_config_error(self) -> None:
        self.configure(lambda r: httpx.Response(200, json={}), api_key="")
        with self.assertRaises(al.ToolError) as ctx:
            self.run_async(self.client.list_workspaces())
        self.assertEqual(error_payload(ctx.exception)["code"], al.CONFIG_ERROR)
        self.assertEqual(self.requests, [], "缺 Key 时不应该发出任何请求")

    def test_unsafe_slug_is_rejected_before_request(self) -> None:
        self.configure(lambda r: httpx.Response(200, json={}))
        for slug in ("../admin", "a b", "", "x" * 100):
            with self.assertRaises(al.ToolError) as ctx:
                self.run_async(self.client.chat(slug, "问题"))
            self.assertEqual(error_payload(ctx.exception)["code"], al.VALIDATION_ERROR)
        self.assertEqual(self.requests, [])

    # ---------- 端点契约 ----------

    def test_list_workspaces_slims_payload(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "workspaces": [
                        {
                            "id": 1,
                            "name": "课程资料",
                            "slug": "course",
                            "chatMode": "chat",
                            "openAiTemp": 0.2,
                            "documents": [{"id": "x", "title": "t"}],
                        }
                    ]
                },
            )

        self.configure(handler)
        result = self.run_async(self.client.list_workspaces())
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["workspaces"][0]["slug"], "course")
        self.assertNotIn("documents", result["workspaces"][0])
        self.assertEqual(self.requests[0].url.path, "/api/v1/workspaces")
        self.assertEqual(self.requests[0].headers["Authorization"], "Bearer test-key")

    def test_chat_posts_slug_as_model(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200, json={"choices": [{"message": {"content": "陈建是作者。"}}]}
            )

        self.configure(handler)
        answer = self.run_async(self.client.chat("course", "陈建是谁？"))
        self.assertEqual(answer, "陈建是作者。")
        body = json.loads(self.requests[0].content)
        self.assertEqual(body["model"], "course")
        self.assertEqual(body["messages"][0]["content"], "陈建是谁？")
        self.assertEqual(self.requests[0].url.path, "/api/v1/openai/chat/completions")

    def test_auth_failure_has_dedicated_code(self) -> None:
        self.configure(lambda r: httpx.Response(401, json={"error": "Invalid API key"}))
        with self.assertRaises(al.ToolError) as ctx:
            self.run_async(self.client.chat("course", "q"))
        payload = error_payload(ctx.exception)
        self.assertEqual(payload["code"], al.AUTH_FAILED)
        self.assertEqual(payload["status"], 401)
        self.assertEqual(payload["detail"], "Invalid API key")

    def test_unreachable_and_timeout(self) -> None:
        def boom(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("refused")

        self.configure(boom)
        with self.assertRaises(al.ToolError) as ctx:
            self.run_async(self.client.list_workspaces())
        self.assertEqual(error_payload(ctx.exception)["code"], al.UPSTREAM_UNREACHABLE)

        def slow(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("slow")

        self.configure(slow)
        with self.assertRaises(al.ToolError) as ctx:
            self.run_async(self.client.list_workspaces())
        self.assertEqual(error_payload(ctx.exception)["code"], al.UPSTREAM_TIMEOUT)

    def test_non_json_is_bad_payload(self) -> None:
        self.configure(lambda r: httpx.Response(200, text="<html>hi</html>"))
        with self.assertRaises(al.ToolError) as ctx:
            self.run_async(self.client.list_workspaces())
        self.assertEqual(error_payload(ctx.exception)["code"], al.UPSTREAM_BAD_PAYLOAD)

    # ---------- 上传 + 向量化 ----------

    def test_upload_then_embed_is_two_requests(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/api/v1/document/upload":
                return httpx.Response(
                    200,
                    json={
                        "success": True,
                        "documents": [{"location": "custom-documents/notes.md-abc.json"}],
                    },
                )
            if request.url.path == "/api/v1/workspace/course/update-embeddings":
                return httpx.Response(200, json={"success": True, "message": "embeddings updated"})
            return httpx.Response(404)

        self.configure(handler)
        result = self.run_async(
            self.client.upload_and_embed_document("course", "notes.md", "# 标题\n正文")
        )
        self.assertEqual(len(self.requests), 2)
        self.assertEqual(
            [r.url.path for r in self.requests],
            ["/api/v1/document/upload", "/api/v1/workspace/course/update-embeddings"],
        )
        # 第二步必须带上第一步拿到的 location，否则文件进不了检索库
        embed_body = json.loads(self.requests[1].content)
        self.assertEqual(embed_body["adds"], ["custom-documents/notes.md-abc.json"])
        self.assertTrue(result["embedded"])
        self.assertTrue(result["message"])

    def test_upload_requires_filename_without_path(self) -> None:
        self.configure(lambda r: httpx.Response(200, json={}))
        for name in ("../x.md", "a/b.md", ""):
            with self.assertRaises(al.ToolError) as ctx:
                self.run_async(
                    self.client.upload_and_embed_document("course", name, "内容")
                )
            self.assertEqual(error_payload(ctx.exception)["code"], al.VALIDATION_ERROR)
        self.assertEqual(self.requests, [])

    def test_upload_without_documents_is_bad_payload(self) -> None:
        self.configure(lambda r: httpx.Response(200, json={"success": True}))
        with self.assertRaises(al.ToolError) as ctx:
            self.run_async(
                self.client.upload_and_embed_document("course", "a.md", "内容")
            )
        self.assertEqual(error_payload(ctx.exception)["code"], al.UPSTREAM_BAD_PAYLOAD)

    # ---------- 向量检索 ----------

    def test_vector_search_payload_and_result(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "results": [
                        {"id": "1", "text": "片段", "score": 0.87, "metadata": {"title": "t"}}
                    ]
                },
            )

        self.configure(handler)
        result = self.run_async(
            self.client.vector_search("course", "陈建", top_n=3, score_threshold=0.5)
        )
        self.assertEqual(result["total"], 1)
        self.assertEqual(self.requests[0].url.path, "/api/v1/workspace/course/vector-search")
        body = json.loads(self.requests[0].content)
        self.assertEqual(body, {"query": "陈建", "topN": 3, "scoreThreshold": 0.5})

    def test_vector_search_rejects_bad_ranges(self) -> None:
        self.configure(lambda r: httpx.Response(200, json={"results": []}))
        with self.assertRaises(al.ToolError) as ctx:
            self.run_async(self.client.vector_search("course", "q", top_n=0))
        self.assertEqual(error_payload(ctx.exception)["code"], al.VALIDATION_ERROR)


class ToolRegistrationTest(unittest.TestCase):
    def test_four_tools_are_registered(self) -> None:
        from mcp_anythingllm.server import mcp

        tools = asyncio.run(mcp.list_tools())
        names = {tool.name for tool in tools}
        self.assertEqual(
            names,
            {"list_workspaces", "workspace_chat", "upload_and_embed_document", "vector_search"},
        )
        for tool in tools:
            self.assertTrue((tool.description or "").strip(), f"{tool.name} 缺少说明")


if __name__ == "__main__":
    unittest.main()
