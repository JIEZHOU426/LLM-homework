"""AGENTS.md project-rules support: load once, inject once, reuse forever.

At session start (first load), if ``AGENTS.md`` exists in the workspace the
whole file is appended to the chat history as a single message and persisted
to the session event log. Later turns simply reuse that message in place, so
prefix tokens never change and the prompt cache stays warm.
"""

from __future__ import annotations

from pathlib import Path

AGENTS_MD_FILENAME = "AGENTS.md"
AGENTS_MD_MAX_BYTES = 1024 * 1024

INJECTION_HEADER = (
    "以下是当前项目根目录中 AGENTS.md 文件的内容。该文件已一次性注入会话，"
    "后续所有轮次都会复用本消息（不会被重复注入）。请在完成任务、回答问题、"
    "编写代码和执行工具调用时遵守其中的项目约定：\n\n"
)


def agents_md_path(workspace_root: Path | str) -> Path:
    return Path(workspace_root) / AGENTS_MD_FILENAME


def read_agents_md(workspace_root: Path | str) -> str:
    """Read and validate ``<workspace>/AGENTS.md``; empty string if absent."""

    path = agents_md_path(workspace_root)
    try:
        if not path.is_file():
            return ""
        if path.stat().st_size > AGENTS_MD_MAX_BYTES:
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                content = handle.read(AGENTS_MD_MAX_BYTES)
        else:
            content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return content.strip()


def build_agents_md_message(content: str) -> dict[str, str]:
    """The chat-history message that carries the AGENTS.md rules."""

    return {
        "role": "system",
        "content": f"{INJECTION_HEADER}<AGENTS.md>\n{content}\n</AGENTS.md>",
    }
