"""Internet search backed by Baidu Qianfan web search API."""

from __future__ import annotations

import json
import socket
from typing import Any, Mapping
from urllib import error, request

from .base import FunctionTool, Tool, ToolSpec
from .common import json_error, json_ok

SEARCH_ENDPOINT = "https://qianfan.baidubce.com/v2/ai_search/web_search"
SEARCH_TIMEOUT_SECONDS = 20
DEFAULT_TOP_K = 10
USER_AGENT = "qAgent/1.0 (+https://cloud.baidu.com/doc/qianfan-api/s/Wmbq4z7e5)"


class SearchError(RuntimeError):
    """Raised when the search API cannot return usable results."""


def _extract_error_message(raw: str) -> str:
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw.strip()[:500]
    if isinstance(payload, dict):
        for key in ("message", "error_msg", "error", "code"):
            value = payload.get(key)
            if value:
                return str(value)
    return raw.strip()[:500]


def _request_search(query: str, api_key: str) -> list[dict[str, Any]]:
    body = json.dumps(
        {
            "messages": [{"role": "user", "content": query}],
            "search_source": "baidu_search_v2",
            "edition": "standard",
            "resource_type_filter": [{"type": "web", "top_k": DEFAULT_TOP_K}],
        },
        ensure_ascii=False,
    ).encode("utf-8")

    http_request = request.Request(
        SEARCH_ENDPOINT,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
    )

    try:
        with request.urlopen(http_request, timeout=SEARCH_TIMEOUT_SECONDS) as response:
            raw = response.read()
    except error.HTTPError as exc:
        detail = (exc.read() or b"").decode("utf-8", errors="replace")
        message = _extract_error_message(detail) or exc.reason
        raise SearchError(f"搜索 API 返回错误（HTTP {exc.code}）：{message}") from exc
    except error.URLError as exc:
        reason = exc.reason
        if isinstance(reason, (socket.timeout, TimeoutError)):
            raise SearchError("搜索服务请求超时，请稍后重试") from exc
        raise SearchError(f"搜索服务网络请求失败：{reason}") from exc
    except (socket.timeout, TimeoutError) as exc:
        raise SearchError("搜索服务请求超时，请稍后重试") from exc
    except OSError as exc:
        raise SearchError(f"搜索服务网络请求失败：{exc}") from exc

    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SearchError("搜索 API 返回了无法解析的响应") from exc

    if not isinstance(payload, dict):
        raise SearchError("搜索 API 返回格式异常：响应不是 JSON 对象")

    code = payload.get("code")
    if code not in (None, "", 0, "0"):
        message = payload.get("message") or payload.get("error_msg") or "未知错误"
        raise SearchError(f"搜索 API 返回错误（code={code}）：{message}")

    references = payload.get("references")
    if references is None:
        return []
    if not isinstance(references, list):
        raise SearchError("搜索 API 返回格式异常：references 不是列表")
    return [item for item in references if isinstance(item, dict)]


def _build_results(references: list[dict[str, Any]]) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    for item in references:
        url = str(item.get("url") or "").strip()
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)

        title = str(item.get("title") or "").strip() or url
        snippet = str(
            item.get("snippet") or item.get("content") or ""
        ).strip()
        result = {"title": title, "url": url}
        if snippet:
            result["snippet"] = snippet
        date = str(item.get("date") or "").strip()
        if date:
            result["date"] = date
        site = str(item.get("website") or item.get("web_anchor") or "").strip()
        if site:
            result["site"] = site
        results.append(result)

    return results


def _search_web(arguments: Mapping[str, Any], api_key: str) -> str:
    raw_query = arguments.get("query")
    if not isinstance(raw_query, str) or not raw_query.strip():
        return json_error("参数 query 必须是非空字符串")

    if not api_key:
        return json_error(
            "未配置百度搜索 API Key：请在 config.ini 的 [search] 小节中设置 "
            "baidu_api_key，或在 .env 中设置 BAIDU_SEARCH_API_KEY。"
        )

    query = raw_query.strip()
    try:
        references = _request_search(query, api_key)
    except SearchError as exc:
        return json_error(str(exc))
    except Exception as exc:  # noqa: BLE001 - the tool must always return JSON
        return json_error(f"搜索失败：{type(exc).__name__}: {exc}")

    results = _build_results(references)
    if not results:
        return json_ok(query=query, summary="", sources=[], message="未找到相关搜索结果")

    summary = "\n\n".join(
        f"[{index}] {result.get('snippet', '')}".strip()
        for index, result in enumerate(results, start=1)
    )
    return json_ok(query=query, summary=summary, sources=results)


def build_search_tools(api_key: str = "") -> list[Tool]:
    def handler(arguments: Mapping[str, Any]) -> str:
        return _search_web(arguments, api_key)

    return [
        FunctionTool(
            ToolSpec(
                name="searchWeb",
                description=(
                    "联网搜索最新信息。接收搜索关键词或问题 query，调用百度千帆"
                    "搜索 API，返回搜索结果摘要以及参考来源的标题和 URL。适合查询"
                    "实时新闻、天气、价格等模型知识之外的最新信息。"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "要搜索的关键词或问题",
                        }
                    },
                    "required": ["query"],
                },
            ),
            handler,
        )
    ]
