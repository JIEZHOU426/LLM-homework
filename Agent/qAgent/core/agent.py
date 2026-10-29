"""The UI-agnostic conversation loop."""

from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator

from openai import AsyncOpenAI

from .config import Settings
from .events import (
    AgentError,
    AgentEvent,
    TextDelta,
    ToolCall,
    ToolCallCompleted,
    ToolCallRequested,
    TurnCompleted,
)
from .llm import create_async_client
from .tools import ToolRegistry, build_default_registry


class ChatAgent:
    """Owns conversation state and exposes turns as an async event stream.

    Front-ends call :meth:`send` and react to the yielded events. They never
    touch the OpenAI client or the tool registry directly.
    """

    def __init__(
        self,
        settings: Settings,
        registry: ToolRegistry | None = None,
        client: AsyncOpenAI | None = None,
    ) -> None:
        self._settings = settings
        self._registry = registry or build_default_registry(
            settings.max_text_bytes,
            settings.baidu_search_api_key,
        )
        self._client = client or create_async_client(settings)
        self._messages: list[dict[str, Any]] = []

    @property
    def messages(self) -> tuple[dict[str, Any], ...]:
        return tuple(self._messages)

    def clear(self) -> None:
        self._messages.clear()

    async def send(self, user_input: str) -> AsyncIterator[AgentEvent]:
        """Run one user turn, including any number of tool round-trips."""

        if not user_input.strip():
            return

        self._messages.append({"role": "user", "content": user_input})

        while True:
            content_parts: list[str] = []
            pending_calls: dict[int, dict[str, Any]] = {}

            try:
                stream = await self._client.chat.completions.create(
                    model=self._settings.model,
                    messages=self._messages,
                    tools=self._registry.schemas(),
                    stream=True,
                )
                async for chunk in stream:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta

                    if delta.content:
                        content_parts.append(delta.content)
                        yield TextDelta(delta.content)

                    if delta.tool_calls:
                        self._accumulate_tool_calls(pending_calls, delta.tool_calls)
            except Exception as exc:  # noqa: BLE001 - surfaced to the front-end
                yield AgentError(f"{type(exc).__name__}: {exc}")
                return

            content = "".join(content_parts)

            if not pending_calls:
                self._messages.append({"role": "assistant", "content": content})
                yield TurnCompleted(content)
                return

            calls = self._finalize_tool_calls(pending_calls)
            self._messages.append(
                {
                    "role": "assistant",
                    "content": content,
                    "tool_calls": [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {
                                "name": call.name,
                                "arguments": call.arguments,
                            },
                        }
                        for call in calls
                    ],
                }
            )

            for call in calls:
                yield ToolCallRequested(call)
                result = await asyncio.to_thread(
                    self._registry.execute,
                    call.name,
                    call.arguments,
                )
                yield ToolCallCompleted(call, result)
                self._messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": result,
                    }
                )

    @staticmethod
    def _accumulate_tool_calls(
        pending: dict[int, dict[str, Any]],
        deltas: Any,
    ) -> None:
        for delta in deltas:
            entry = pending.setdefault(
                delta.index,
                {
                    "id": "",
                    "type": "function",
                    "function": {"name": "", "arguments": ""},
                },
            )
            if delta.id:
                entry["id"] = delta.id
            if delta.type:
                entry["type"] = delta.type
            if delta.function:
                if delta.function.name:
                    entry["function"]["name"] += delta.function.name
                if delta.function.arguments:
                    entry["function"]["arguments"] += delta.function.arguments

    @staticmethod
    def _finalize_tool_calls(pending: dict[int, dict[str, Any]]) -> list[ToolCall]:
        calls = []
        for index in sorted(pending):
            entry = pending[index]
            calls.append(
                ToolCall(
                    id=entry["id"],
                    name=entry["function"]["name"],
                    arguments=entry["function"]["arguments"] or "{}",
                )
            )
        return calls
