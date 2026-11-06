"""recallContext: keyword search over archived raw conversations.

After a compaction the full original messages live in
``<workspace>/.agents/context/<stamp>.jsonl``. This tool gives the model a
plain full-text way to look details back up — no embeddings, no vector DB.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from ..compact import archive_identifier, context_directory
from .base import FunctionTool, Tool, ToolSpec
from .common import json_error

MAX_MATCHES = 20
SNIPPET_WINDOW = 160
MAX_RESULT_CHARS = 6000


class RecallContextTools:
    def __init__(self, workspace_root: Path | None = None) -> None:
        self._workspace_root = workspace_root

    def build(self) -> list[Tool]:
        return [
            FunctionTool(
                ToolSpec(
                    name="recallContext",
                    description=(
                        "检索此前上下文压缩时保存的原始对话归档"
                        "（.agents/context/ 目录下的 jsonl 文件）。"
                        "text 必填：需要查找的关键词或文本内容，多个关键词用空格分隔"
                        "（结果必须同时包含全部关键词）；"
                        "id 可选：归档编号（如 20261022-153000），"
                        "不提供 id 时检索全部归档。"
                        "返回匹配的原始内容片段、归档编号和所在位置。"
                    ),
                    parameters={
                        "type": "object",
                        "properties": {
                            "id": {
                                "type": "string",
                                "description": "归档编号，例如 20261022-153000；省略时检索全部归档",
                            },
                            "text": {
                                "type": "string",
                                "description": "要查找的关键词或文本内容，多个关键词用空格分隔",
                            },
                        },
                        "required": ["text"],
                    },
                ),
                self._recall,
            ),
        ]

    def _recall(self, arguments: Mapping[str, Any]) -> str:
        text = arguments.get("text")
        if not isinstance(text, str) or not text.strip():
            return json_error("缺少参数: text")
        archive_id = arguments.get("id")
        if archive_id is not None and not isinstance(archive_id, str):
            return json_error("参数 id 必须是字符串")

        root = self._workspace_root or Path.cwd()
        directory = context_directory(root)
        files = sorted(directory.glob("*.jsonl"))
        if not files:
            return json_error(
                f"归档目录不存在或为空：{directory}。"
                "只有执行过 /compact 后才有可检索的归档。"
            )

        if archive_id:
            target_id = archive_id.strip()
            selected = [p for p in files if p.stem == target_id]
            if not selected:
                return json_error(
                    f"找不到归档编号 {target_id}。可用的归档编号："
                    + ", ".join(archive_identifier(p) for p in files)
                )
            files = selected

        keywords = [kw.casefold() for kw in text.split()]
        if not keywords:
            keywords = [text.casefold()]

        matches: list[dict[str, Any]] = []
        total_matches = 0
        budget = MAX_RESULT_CHARS
        for path in files:
            for record in _read_archive(path):
                content = _record_search_text(record)
                folded = content.casefold()
                if not all(keyword in folded for keyword in keywords):
                    continue
                total_matches += 1
                if len(matches) >= MAX_MATCHES or budget <= len("…"):
                    continue
                snippet, start, end = _build_snippet(content, folded, keywords)
                matches.append(
                    {
                        "archive": archive_identifier(path),
                        "message_index": record.get("index"),
                        "role": record.get("role"),
                        "position": {"start": start, "end": end},
                        "snippet": snippet,
                    }
                )
                budget -= len(snippet)

        result: dict[str, Any] = {
            "query": {"text": text, "id": archive_id},
            "archives_searched": len(files),
            "total_matches": total_matches,
            "returned_matches": len(matches),
            "matches": matches,
        }
        if total_matches > len(matches):
            result["truncated"] = True
            result["hint"] = (
                "匹配内容较多已截断，请使用更精确的关键词，"
                "或提供 id 只检索单个归档。"
            )
        elif not matches:
            result["hint"] = "未找到匹配内容，可尝试更短或更常见的关键词。"
        return json.dumps(result, ensure_ascii=False)


def _read_archive(path: Path):
    try:
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(record, dict) and record.get("type") == "message":
                    yield record
    except OSError:
        return


def _record_search_text(record: dict[str, Any]) -> str:
    """Readable, searchable text of one archived message record."""

    parts: list[str] = []
    content = record.get("content")
    if isinstance(content, str):
        parts.append(content)
    elif content is not None:
        parts.append(json.dumps(content, ensure_ascii=False))
    for call in record.get("tool_calls") or []:
        function = call.get("function") or {}
        parts.append(function.get("name") or "")
        parts.append(function.get("arguments") or "")
    if record.get("tool_call_id"):
        parts.append(str(record["tool_call_id"]))
    return "\n".join(part for part in parts if part)


def _build_snippet(
    text: str,
    folded: str,
    keywords: list[str],
) -> tuple[str, int, int]:
    positions = [folded.find(keyword) for keyword in keywords]
    first = min(pos for pos in positions if pos >= 0)
    start = max(0, first - SNIPPET_WINDOW)
    end = min(len(text), first + SNIPPET_WINDOW)
    snippet = ""
    if start > 0:
        snippet += "…"
    snippet += text[start:end]
    if end < len(text):
        snippet += "…"
    return snippet, start, end
