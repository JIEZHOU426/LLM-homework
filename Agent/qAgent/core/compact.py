"""Context compaction helpers.

This module keeps the *simple* pieces of the compaction feature: token
estimation without any external tokenizer, JSONL archiving of the raw
conversation, and the summarization system prompt. The orchestration lives in
:mod:`core.agent`; this module must stay free of LLM/UI dependencies.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

CONTEXT_DIR_PARTS = (".agents", "context")


def archive_name_stamp(now: datetime | None = None) -> str:
    """File-stamp used for archive names, e.g. ``20261022-153000``."""

    return (now or datetime.now()).strftime("%Y%m%d-%H%M%S")


def context_directory(workspace_root: Path | str) -> Path:
    """The ``<workspace>/.agents/context`` archive directory."""

    return Path(workspace_root) / Path(*CONTEXT_DIR_PARTS)


def archive_messages(
    workspace_root: Path | str,
    messages: list[dict[str, Any]],
    *,
    meta: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> Path:
    """Write the full raw conversation to ``.agents/context/<stamp>.jsonl``.

    One JSON object per line: a ``meta`` header line first, then every message
    in order with its role, content, tool-call arguments and tool results kept
    exactly as stored in the conversation history.
    """

    directory = context_directory(workspace_root)
    directory.mkdir(parents=True, exist_ok=True)

    stamp = archive_name_stamp(now)
    path = directory / f"{stamp}.jsonl"
    counter = 1
    while path.exists():
        path = directory / f"{stamp}-{counter}.jsonl"
        counter += 1

    header = {
        "type": "meta",
        "archived_at": (now or datetime.now()).isoformat(timespec="seconds"),
        "message_count": len(messages),
        **(meta or {}),
    }
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(header, ensure_ascii=False) + "\n")
        for index, message in enumerate(messages):
            record = {"type": "message", "index": index, **message}
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return path


# --- Token estimation -------------------------------------------------------
# A rough heuristic: CJK characters cost ~1 token each, non-CJK text costs
# ~1 token per 4 characters, plus per-message framing overhead. Good enough
# for a 60% threshold warning; the API's own usage numbers are preferred
# whenever they are available.


def _is_wide(ch: str) -> bool:
    code = ord(ch)
    return (
        0x4E00 <= code <= 0x9FFF  # CJK 统一表意文字
        or 0x3400 <= code <= 0x4DBF  # CJK 扩展 A
        or 0x3000 <= code <= 0x303F  # CJK 标点
        or 0xFF00 <= code <= 0xFFEF  # 全角符号
        or 0x2000 <= code <= 0x206F  # 常用标点/破折号区间
    )


def estimate_text_tokens(text: str | None) -> int:
    if not text:
        return 0
    wide = sum(1 for ch in text if _is_wide(ch))
    narrow = len(text) - wide
    return wide + (narrow + 3) // 4


def estimate_message_tokens(message: dict[str, Any]) -> int:
    total = 4  # role 标记与消息框架开销
    total += estimate_text_tokens(message.get("content"))
    for call in message.get("tool_calls") or []:
        function = call.get("function") or {}
        total += estimate_text_tokens(function.get("name"))
        total += estimate_text_tokens(function.get("arguments"))
    if message.get("tool_call_id"):
        total += 3
    return total


def estimate_messages_tokens(messages: list[dict[str, Any]]) -> int:
    return sum(estimate_message_tokens(message) for message in messages)


# --- TUI 压缩面板用：压缩前会话的可读转录 --------------------------


def format_transcript(messages: list[dict[str, Any]]) -> str:
    """Human-readable transcript used by the compaction result panel."""

    lines: list[str] = []
    for index, message in enumerate(messages, start=1):
        role = message.get("role", "unknown")
        lines.append(f"## [{index}] {_ROLE_LABELS.get(role, role)}")
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            lines.append(content.strip())
        elif content is not None:
            lines.append(f"```json\n{json.dumps(content, ensure_ascii=False)}\n```")
        for call in message.get("tool_calls") or []:
            function = call.get("function") or {}
            lines.append(
                f"- **调用工具 `{function.get('name', '?')}`**\n"
                f"  ```json\n  {function.get('arguments') or '{}'}\n  ```"
            )
        if message.get("tool_call_id"):
            lines.append(f"- 工具返回结果（call_id={message['tool_call_id']}）")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


_ROLE_LABELS = {
    "system": "system（系统提示）",
    "user": "user（用户）",
    "assistant": "assistant（助手）",
    "tool": "tool（工具结果）",
}


def archive_identifier(path: Path) -> str:
    """Archive number, e.g. ``20261022-153000`` for ``20261022-153000.jsonl``."""

    return path.stem


SUMMARY_SYSTEM_PROMPT = """\
你是一名 AI Agent 的上下文管理助手。当前会话即将达到上下文窗口限制，需要将历史对话压缩为一份高质量的工作摘要，以便 Agent 在新的上下文中继续执行任务。

请认真阅读提供的历史上下文，提取对后续工作仍然有价值的信息，并生成一份约 5,000 Tokens 的 Markdown 摘要。

摘要应重点保留以下内容：

1. **用户目标与要求**：用户希望完成什么任务？有哪些必须遵守的约束、偏好和验收条件？
2. **已经完成的工作**：哪些任务已经完成？实现了哪些功能？获得了哪些已经验证的结果？
3. **当前工作状态**：Agent 正在处理什么任务？当前进展到哪一步？是否存在尚未解决的问题？
4. **关键技术信息**：保留重要的文件路径、函数名称、接口定义、配置项、执行命令、错误信息和必要的代码片段。
5. **关键决策与原因**：记录用户和 Agent 已经确定的技术方案，以及重要的设计取舍。
6. **下一步任务**：明确接下来应该执行的操作，以及需要继续验证的事项。

请遵守以下要求：

- 优先保留对后续任务有直接影响的信息，删除寒暄、重复讨论、过时的尝试和无关内容。
- 对已经验证的事实与尚未验证的推测作出明确区分。
- 不要将计划完成的任务描述为已经完成。
- 重要的文件路径、函数名称、配置名称和命令应保留准确原文。
- 对失败的尝试，只保留有助于避免重复错误的信息。
- 如果信息存在冲突，应优先保留用户最新确认的要求，并简要说明仍然存在的冲突。
- 如果某些历史细节无法在摘要中完整保留，可简要说明它们已保存到原始上下文归档中，后续可以通过 `recallContext` 工具重新检索。
- 使用清晰的 Markdown 结构输出摘要，不要附加解释或无关内容。

**最终目标：使一个从未阅读过原始对话的 Agent，仅凭这份摘要，就能够理解当前任务、继承关键决策，并继续开展工作。**
"""
