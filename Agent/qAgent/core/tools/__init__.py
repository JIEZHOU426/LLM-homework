"""Tool system.

Use :func:`build_default_registry` from the composition root. Tools never
import front-end code, and the agent only depends on the ``ToolRegistry``
contract.
"""

from __future__ import annotations

from .base import FunctionTool, Tool, ToolSpec
from .clock import build_clock_tools
from .filesystem import FileSystemTools
from .registry import ToolRegistry
from .search import build_search_tools
from .web import build_web_tools


def build_default_registry(
    max_text_bytes: int,
    baidu_search_api_key: str = "",
) -> ToolRegistry:
    tools: list[Tool] = build_clock_tools()
    tools.extend(FileSystemTools(max_text_bytes).build())
    tools.extend(build_web_tools())
    tools.extend(build_search_tools(baidu_search_api_key))
    return ToolRegistry(tools)


__all__ = [
    "FileSystemTools",
    "FunctionTool",
    "Tool",
    "ToolRegistry",
    "ToolSpec",
    "build_clock_tools",
    "build_default_registry",
    "build_search_tools",
    "build_web_tools",
]
