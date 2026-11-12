"""Tool system.

Use :func:`build_default_registry` from the composition root. Tools never
import front-end code, and the agent only depends on the ``ToolRegistry``
contract.
"""

from __future__ import annotations

from pathlib import Path

from ..call_log import ToolCallLog
from ..skills import SkillCatalog
from .base import FunctionTool, Tool, ToolSpec
from .clock import build_clock_tools
from .filesystem import FileSystemTools
from .mcp_client import (
    McpConnectReport,
    McpServerStatus,
    McpTool,
    McpToolManager,
)
from .registry import ToolRegistry
from .recall import RecallContextTools
from .search import build_search_tools
from .skills import build_create_skill_tool, build_skill_tool
from .web import build_web_tools


def build_default_registry(
    max_text_bytes: int,
    baidu_search_api_key: str = "",
    skills: SkillCatalog | None = None,
    workspace_root: Path | None = None,
    confine_paths: bool = True,
    tool_log: ToolCallLog | None = None,
) -> ToolRegistry:
    """Registered on every front-end.

    ``workspace_root`` feeds both ``recallContext`` and the file tools' path
    boundary: with ``confine_paths`` (the default) every file argument must
    resolve inside it, otherwise the tool refuses with ``PATH_OUTSIDE_WORKSPACE``.
    ``tool_log`` receives one JSONL line per tool call.
    """
    root = Path(workspace_root) if workspace_root is not None else Path.cwd()
    catalog = (
        skills
        if skills is not None
        else SkillCatalog.discover(root, max_text_bytes)
    )
    tools: list[Tool] = build_clock_tools()
    tools.extend(
        FileSystemTools(
            max_text_bytes,
            workspace_root=root,
            confine=confine_paths,
        ).build()
    )
    tools.extend(build_web_tools())
    tools.extend(build_search_tools(baidu_search_api_key))
    tools.append(build_skill_tool(catalog))
    tools.append(build_create_skill_tool(catalog))
    tools.extend(RecallContextTools(root).build())
    return ToolRegistry(tools, tool_log=tool_log)


__all__ = [
    "FileSystemTools",
    "FunctionTool",
    "McpConnectReport",
    "McpServerStatus",
    "McpTool",
    "McpToolManager",
    "RecallContextTools",
    "Tool",
    "ToolRegistry",
    "ToolSpec",
    "build_clock_tools",
    "build_create_skill_tool",
    "build_default_registry",
    "build_search_tools",
    "build_skill_tool",
    "build_web_tools",
]
