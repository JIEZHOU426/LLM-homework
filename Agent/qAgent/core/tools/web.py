"""Web page fetching and main-content extraction."""

from __future__ import annotations

import shutil
import subprocess
from typing import Any, Mapping
from urllib.parse import urlparse

import trafilatura

from .base import FunctionTool, Tool, ToolSpec
from .common import json_error, json_ok

FETCH_TIMEOUT_SECONDS = 30
MAX_HTML_BYTES = 5 * 1024 * 1024
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36 qAgent/1.0"
)


def _validate_url(raw: str) -> str:
    url = raw.strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("url 必须是有效的 http 或 https 地址")
    return url


def _download_html(url: str) -> bytes:
    curl = shutil.which("curl")
    if not curl:
        raise RuntimeError("未找到本地 curl 程序，请先安装 curl")

    command = [
        curl,
        "--silent",
        "--show-error",
        "--fail",
        "--location",
        "--compressed",
        "--connect-timeout",
        "10",
        "--max-time",
        str(FETCH_TIMEOUT_SECONDS),
        "--max-filesize",
        str(MAX_HTML_BYTES),
        "--proto",
        "=http,https",
        "--proto-redir",
        "=http,https",
        "--user-agent",
        USER_AGENT,
        url,
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            timeout=FETCH_TIMEOUT_SECONDS + 5,
            check=False,
            shell=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("下载网页超时") from exc
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(f"无法执行 curl: {exc}") from exc

    if result.returncode != 0:
        stderr = (result.stderr or b"").decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"网页访问失败: {stderr or f'curl 退出码 {result.returncode}'}")

    html = result.stdout or b""
    if not html:
        raise RuntimeError("网页访问失败: 返回内容为空")
    return html


def _extract_markdown(html: bytes, url: str) -> str:
    try:
        document = trafilatura.load_html(html, max_size=MAX_HTML_BYTES)
    except Exception as exc:  # noqa: BLE001 - normalize parser errors for the model
        raise RuntimeError(f"HTML 解析失败: {exc}") from exc

    if document is None:
        raise RuntimeError("HTML 解析失败: 无法解析网页结构")

    try:
        markdown = trafilatura.extract(
            document,
            url=url,
            output_format="markdown",
            include_comments=False,
            include_tables=True,
            include_links=True,
            include_formatting=True,
            include_images=False,
            deduplicate=True,
            favor_recall=True,
        )
    except Exception as exc:  # noqa: BLE001 - normalize extraction errors
        raise RuntimeError(f"正文提取失败: {exc}") from exc

    if not markdown or not markdown.strip():
        raise RuntimeError("正文提取失败: 未找到可用的正文内容")
    return markdown.strip()


def _fetchweb(arguments: Mapping[str, Any]) -> str:
    raw_url = arguments.get("url")
    if not isinstance(raw_url, str):
        return json_error("参数 url 必须是字符串")

    try:
        url = _validate_url(raw_url)
        html = _download_html(url)
        markdown = _extract_markdown(html, url)
    except (ValueError, RuntimeError, OSError) as exc:
        return json_error(str(exc))
    except Exception as exc:  # noqa: BLE001 - the tool must always return JSON
        return json_error(f"网页获取失败: {type(exc).__name__}: {exc}")

    return json_ok(url=url, markdown=markdown)


def build_web_tools() -> list[Tool]:
    return [
        FunctionTool(
            ToolSpec(
                name="fetchweb",
                description=(
                    "获取指定网页的主要内容。接收网页 URL，下载 HTML 后提取正文并"
                    "转换为 Markdown，保留标题、段落、列表、表格和链接，去除导航栏、"
                    "广告、页脚等无关内容，适合阅读文章或整理网页资料。"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "要获取内容的网页地址，必须是 http 或 https URL",
                        }
                    },
                    "required": ["url"],
                },
            ),
            _fetchweb,
        )
    ]
