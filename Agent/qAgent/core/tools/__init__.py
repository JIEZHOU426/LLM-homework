"""Tool system.

Use :func:`build_default_registry` from the composition root. Tools never
import front-end code, and the agent only depends on the ``ToolRegistry``
contract.
"""

from __future__ import annotations

from pathlib import Path

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
) -> ToolRegistry:
    """Registered on every front-end; ``workspace_root`` feeds recallContext."""
    catalog = (
        skills
        if skills is not None
        else SkillCatalog.discover(Path.cwd(), max_text_bytes)
    )
    tools: list[Tool] = build_clock_tools()
    tools.extend(FileSystemTools(max_text_bytes).build())
    tools.extend(build_web_tools())
    tools.extend(build_search_tools(baidu_search_api_key))
    tools.append(build_skill_tool(catalog))
    tools.append(build_create_skill_tool(catalog))
    tools.extend(RecallContextTools(workspace_root).build())
    return ToolRegistry(tools)


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
