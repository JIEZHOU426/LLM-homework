"""Project-rules file (``AGENT.md``) support: load once, inject once, reuse.

At session start (first load), if the rules file exists in the workspace the
whole file is appended to the chat history as a single message and persisted
to the session event log. Later turns simply reuse that message in place, so
prefix tokens never change and the prompt cache stays warm.

The file name is configurable (``[agents] filename`` / ``QAGENT_AGENTS_FILE``).
Whatever it is configured to, ``AGENT.md`` and ``AGENTS.md`` are also probed
as equivalent names, because both spellings are in the wild.
"""

from __future__ import annotations

from pathlib import Path

AGENTS_MD_FILENAME = "AGENT.md"
AGENTS_MD_ALIASES = ("AGENT.md", "AGENTS.md")
AGENTS_MD_MAX_BYTES = 1024 * 1024

INJECTION_HEADER = (
    "以下是当前项目根目录中项目规则文件（AGENT.md / AGENTS.md）的内容。"
    "该文件已一次性注入会话，后续所有轮次都会复用本消息（不会被重复注入）。"
    "请在完成任务、回答问题、编写代码和执行工具调用时遵守其中的项目约定：\n\n"
)


def candidate_names(filename: str | None = None) -> tuple[str, ...]:
    """File names to probe, in priority order, without duplicates.

    The two standard spellings are aliases of each other, so configuring one
    probes the other as a fallback. A custom name is probed on its own —
    silently reading ``AGENTS.md`` because a custom file is missing would be
    confusing.
    """

    name = filename.strip() if filename and filename.strip() else ""
    if not name:
        return AGENTS_MD_ALIASES
    if name in AGENTS_MD_ALIASES:
        return (name,) + tuple(a for a in AGENTS_MD_ALIASES if a != name)
    return (name,)


def agents_md_path(
    workspace_root: Path | str,
    filename: str | None = None,
) -> Path:
    """Path of the rules file (the configured name, not yet probed for aliases)."""

    name = filename.strip() if filename and filename.strip() else AGENTS_MD_FILENAME
    return Path(workspace_root) / name


def resolve_agents_md_path(
    workspace_root: Path | str,
    filename: str | None = None,
) -> Path | None:
    """First existing rules file in the workspace, or ``None``."""

    for name in candidate_names(filename):
        path = Path(workspace_root) / name
        if path.is_file():
            return path
    return None


def read_agents_md(
    workspace_root: Path | str,
    filename: str | None = None,
) -> str:
    """Read and validate the rules file; empty string when absent or unreadable."""

    path = resolve_agents_md_path(workspace_root, filename)
    if path is None:
        return ""
    try:
        if path.stat().st_size > AGENTS_MD_MAX_BYTES:
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                content = handle.read(AGENTS_MD_MAX_BYTES)
        else:
            content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return content.strip()


def build_agents_md_message(content: str, filename: str = AGENTS_MD_FILENAME) -> dict[str, str]:
    """The chat-history message that carries the project rules."""

    return {
        "role": "system",
        "content": (
            f"{INJECTION_HEADER}<{filename}>\n{content}\n</{filename}>"
        ),
    }
