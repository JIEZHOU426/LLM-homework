"""Tool registration, schema export and safe dispatch."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Iterable

from .base import Tool
from .common import json_error


class ToolRegistry:
    """Keeps tools decoupled from the conversation loop."""

    def __init__(self, tools: Iterable[Tool] = ()) -> None:
        self._tools: dict[str, Tool] = {}
        for tool in tools:
            self.register(tool)

    def register(self, tool: Tool) -> None:
        name = tool.spec.name
        if name in self._tools:
            raise ValueError(f"工具已注册: {name}")
        self._tools[name] = tool

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: object) -> bool:
        return name in self._tools

    def schemas(self) -> list[dict[str, Any]]:
        return [tool.spec.as_openai_schema() for tool in self._tools.values()]

    def _resolve(
        self,
        name: str,
        raw_arguments: str,
    ) -> tuple[Tool, dict[str, Any]] | str:
        """Shared validation for both sync and async dispatch."""

        try:
            arguments = json.loads(raw_arguments or "{}")
            if not isinstance(arguments, dict):
                return json_error("工具参数必须是 JSON 对象")
        except json.JSONDecodeError as exc:
            return json_error(f"参数解析失败: {exc}")

        tool = self._tools.get(name)
        if tool is None:
            return json_error(f"未知工具: {name}")

        missing = [
            key
            for key in tool.spec.parameters.get("required", [])
            if key not in arguments
        ]
        if missing:
            return json_error(f"缺少参数: {', '.join(missing)}")
        return tool, arguments

    async def aexecute(self, name: str, raw_arguments: str) -> str:
        """Async dispatch: await async-aware tools, off-load sync ones."""

        resolved = self._resolve(name, raw_arguments)
        if isinstance(resolved, str):
            return resolved
        tool, arguments = resolved

        try:
            run_async = getattr(tool, "run_async", None)
            if run_async is not None:
                return await run_async(arguments)
            return await asyncio.to_thread(tool.run, arguments)
        except Exception as exc:  # noqa: BLE001 - errors are data for the model
            return json_error(str(exc))

    def execute(self, name: str, raw_arguments: str) -> str:
        """Parse model-provided JSON, validate required fields and dispatch."""

        resolved = self._resolve(name, raw_arguments)
        if isinstance(resolved, str):
            return resolved
        tool, arguments = resolved

        try:
            return tool.run(arguments)
        except Exception as exc:  # noqa: BLE001 - errors are data for the model
            return json_error(str(exc))
