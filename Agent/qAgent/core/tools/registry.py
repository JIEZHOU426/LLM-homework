"""Tool registration, schema export and safe dispatch."""

from __future__ import annotations

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

    def schemas(self) -> list[dict[str, Any]]:
        return [tool.spec.as_openai_schema() for tool in self._tools.values()]

    def execute(self, name: str, raw_arguments: str) -> str:
        """Parse model-provided JSON, validate required fields and dispatch."""

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

        try:
            return tool.run(arguments)
        except Exception as exc:  # noqa: BLE001 - errors are data for the model
            return json_error(str(exc))
