"""Tool registration, schema export and safe dispatch."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Iterable

from ..call_log import ToolCallLog
from .base import Tool
from .common import json_error


class ToolRegistry:
    """Keeps tools decoupled from the conversation loop."""

    def __init__(
        self,
        tools: Iterable[Tool] = (),
        tool_log: ToolCallLog | None = None,
    ) -> None:
        self._tools: dict[str, Tool] = {}
        self._log = tool_log
        for tool in tools:
            self.register(tool)

    @property
    def tool_log(self) -> ToolCallLog | None:
        return self._log

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
            self._record(name, resolved, 0, raw_arguments)
            return resolved
        tool, arguments = resolved

        started = time.perf_counter()
        try:
            run_async = getattr(tool, "run_async", None)
            if run_async is not None:
                result = await run_async(arguments)
            else:
                result = await asyncio.to_thread(tool.run, arguments)
        except Exception as exc:  # noqa: BLE001 - errors are data for the model
            result = json_error(str(exc))
        self._record(name, result, started, arguments)
        return result

    def execute(self, name: str, raw_arguments: str) -> str:
        """Parse model-provided JSON, validate required fields and dispatch."""

        resolved = self._resolve(name, raw_arguments)
        if isinstance(resolved, str):
            self._record(name, resolved, 0, raw_arguments)
            return resolved
        tool, arguments = resolved

        started = time.perf_counter()
        try:
            result = tool.run(arguments)
        except Exception as exc:  # noqa: BLE001 - errors are data for the model
            result = json_error(str(exc))
        self._record(name, result, started, arguments)
        return result

    def _record(
        self,
        name: str,
        result: str,
        started: float | None,
        arguments: Any,
    ) -> None:
        """Append one line to the tool-call journal (never raises)."""

        if self._log is None:
            return
        dur_ms = 0
        if isinstance(started, float):
            dur_ms = int((time.perf_counter() - started) * 1000)
        parsed: Any = arguments
        if isinstance(arguments, str):
            try:
                parsed = json.loads(arguments or "{}")
            except json.JSONDecodeError:
                parsed = None
        self._log.record(
            name,
            ok=not result.startswith('{"error"'),
            dur_ms=dur_ms,
            result=result,
            arguments=parsed,
        )
