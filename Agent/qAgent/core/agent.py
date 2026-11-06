"""The UI-agnostic conversation loop."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator

from openai import AsyncOpenAI, BadRequestError

from .agents_md import (
    build_agents_md_message,
    read_agents_md,
)
from .compact import (
    SUMMARY_SYSTEM_PROMPT,
    archive_identifier,
    archive_messages,
    estimate_messages_tokens,
    estimate_message_tokens,
    format_transcript,
)
from .config import DEFAULT_CONTEXT_WINDOW, Settings
from .events import (
    AgentError,
    AgentEvent,
    CompactionCompleted,
    CompactionFailed,
    CompactionStarted,
    ContextWarning,
    TextDelta,
    ToolCall,
    ToolCallCompleted,
    ToolCallRequested,
    TurnCompleted,
)
from .llm import create_async_client
from .skills import SkillCatalog
from .tools import ToolRegistry, build_default_registry
from .tools.mcp_client import McpConnectReport, McpToolManager


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
        skills: SkillCatalog | None = None,
    ) -> None:
        self._settings = settings
        self._skills = (
            skills
            if skills is not None
            else SkillCatalog.discover(
                settings.workspace_root,
                settings.max_text_bytes,
            )
        )
        self._registry = registry or build_default_registry(
            settings.max_text_bytes,
            settings.baidu_search_api_key,
            self._skills,
            settings.workspace_root,
        )
        self._client = client or create_async_client(settings)
        self._mcp_manager: McpToolManager | None = None
        self._agents_md: str = read_agents_md(settings.workspace_root)
        self._system_message = self._build_system_message()
        self._messages: list[dict[str, Any]] = []
        self._compacting = False
        self._paused = False
        self._last_usage: dict[str, int] | None = None
        self.clear()

    @property
    def messages(self) -> tuple[dict[str, Any], ...]:
        return tuple(self._messages)

    @property
    def skills(self) -> SkillCatalog:
        return self._skills

    @property
    def agents_md(self) -> str:
        """The AGENTS.md content injected into this session ("" = none)."""
        return self._agents_md

    @property
    def tool_count(self) -> int:
        return len(self._registry)

    @property
    def context_window(self) -> int:
        """Context window; falls back to 128k (flagged as 默认) if unknown."""
        return self._settings.context_window or DEFAULT_CONTEXT_WINDOW

    @property
    def context_window_is_default(self) -> bool:
        return self._settings.context_window <= 0

    @property
    def compact_threshold(self) -> float:
        return self._settings.compact_threshold

    @property
    def is_paused(self) -> bool:
        """True once usage crossed the threshold and before a compaction."""
        return self._paused

    @property
    def is_compacting(self) -> bool:
        return self._compacting

    def context_info(self) -> dict[str, Any]:
        """A snapshot used by front-ends to render context usage."""
        limit = self.context_window  # 未知窗口时回落到 128k（标记为默认）
        used = self.current_context_tokens()
        return {
            "used": used,
            "limit": limit,
            "default": self.context_window_is_default,
            "ratio": (used / limit) if limit > 0 else 0.0,
            "threshold": self._settings.compact_threshold,
            "paused": self._paused,
            "compacting": self._compacting,
        }

    def current_context_tokens(self) -> int:
        """Tokens of system prompt + user prompts + history + tool messages.

        Prefers the prompt/completion usage reported by the model API and adds
        an estimate for messages appended after that request (tool results).
        Falls back to a pure estimate when no API usage is available.
        """
        if self._last_usage is not None:
            tail = self._messages[self._last_usage["after_index"]:]
            extra = sum(estimate_message_tokens(m) for m in tail)
            return self._last_usage["prompt"] + self._last_usage["completion"] + extra
        return estimate_messages_tokens(self._messages)

    async def connect_mcp(self) -> McpConnectReport:
        """Connect MCP servers declared in the workspace ``.mcp.json``.

        Successfully discovered tools are registered into the shared registry;
        failed servers are reported without affecting anything else.
        """
        manager = McpToolManager(
            request_timeout=self._settings.mcp_request_timeout,
            connect_timeout=self._settings.mcp_connect_timeout,
        )
        report = await manager.connect_from_config(self._settings.workspace_root)
        if manager.has_tools():
            manager.register_into(self._registry)
            self._mcp_manager = manager
        else:
            await manager.aclose()
        return report

    def mcp_snapshot(self) -> list[dict[str, Any]]:
        """Sidebar data: per-server connection status and exposed tools."""

        if self._mcp_manager is None:
            return []
        return self._mcp_manager.snapshot()

    async def close_mcp(self) -> None:
        """Shut down every MCP connection (called when the front-end quits)."""
        if self._mcp_manager is not None:
            await self._mcp_manager.aclose()
            self._mcp_manager = None

    def clear(self) -> None:
        """Start a fresh session: system prompt + one-shot AGENTS.md."""
        self._messages.clear()
        self._paused = False
        self._last_usage = None
        self._compacting = False
        if self._system_message is not None:
            self._messages.append(dict(self._system_message))
        self._inject_agents_md(self._agents_md)

    def _inject_agents_md(self, content: str) -> None:
        """Append the AGENTS.md message once, at the head of the history."""
        if not content:
            return
        self._messages.append(build_agents_md_message(content))

    def restore(self, *, agents_md: str | None, messages: list[dict[str, Any]]) -> None:
        """Rebuild a session from its persisted event log.

        ``agents_md`` is the content recorded in the log's ``agents_md`` event
        (so a restored session reuses the original message, keeping prompt
        prefix tokens stable). When the log had none, the current workspace
        file is used instead. Persisted ``system`` role messages are dropped —
        the system prompt is rebuilt from the live skill catalog.
        """
        self._agents_md = (agents_md or "").strip()
        if not self._agents_md and not messages:
            self.clear()
            return
        self._messages.clear()
        self._paused = False
        self._last_usage = None
        self._compacting = False
        if self._system_message is not None:
            self._messages.append(dict(self._system_message))
        if not self._agents_md and self._system_message is None:
            # No skills prompt either; still honour an on-disk AGENTS.md.
            self._agents_md = read_agents_md(self._settings.workspace_root)
        self._inject_agents_md(self._agents_md)
        for message in messages:
            if message.get("role") == "system":
                continue
            self._messages.append(dict(message))

    def _build_system_message(self) -> dict[str, Any] | None:
        prompt = self._skills.system_prompt()
        if not prompt:
            return None
        return {"role": "system", "content": prompt}

    async def send(self, user_input: str) -> AsyncIterator[AgentEvent]:
        """Run one user turn, including any number of tool round-trips."""

        if not user_input.strip():
            return
        if self._compacting:
            yield AgentError("上下文正在压缩中，请等待压缩完成后继续。")
            return
        if self._paused:
            info = self.context_info()
            yield AgentError(
                "上下文使用量已达 "
                f"{info['used']}/{info['limit']} tokens"
                "（超过阈值 "
                f"{round(self._settings.compact_threshold * 100)}%），"
                "已暂停接受新的提示词。请输入 /compact 压缩上下文后再继续。"
            )
            return

        self._messages.append({"role": "user", "content": user_input})

        while True:
            content_parts: list[str] = []
            pending_calls: dict[int, dict[str, Any]] = {}
            snapshot = len(self._messages)

            try:
                stream = await self._request_stream(messages=self._messages)
                async for chunk in stream:
                    if not chunk.choices:
                        # The final stream chunk carries usage and no choices.
                        self._capture_usage(chunk.usage, snapshot)
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
                self._mark_usage_upto_appended()
                yield TurnCompleted(content)
                warning = self._threshold_warning()
                if warning is not None:
                    yield warning
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
            self._mark_usage_upto_appended()

            for call in calls:
                yield ToolCallRequested(call)
                result = await self._registry.aexecute(call.name, call.arguments)
                yield ToolCallCompleted(call, result)
                self._messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": result,
                    }
                )

    async def _request_stream(self, *, messages: list[dict[str, Any]]):
        """Stream a completion, preferring API usage stats when supported."""

        options = dict(
            model=self._settings.model,
            messages=messages,
            tools=self._registry.schemas(),
            stream=True,
        )
        try:
            return await self._client.chat.completions.create(
                **options,
                stream_options={"include_usage": True},
            )
        except (BadRequestError, TypeError):
            # Provider rejected stream_options; fall back to plain streaming.
            return await self._client.chat.completions.create(**options)

    def _capture_usage(self, usage: Any, snapshot: int) -> None:
        if usage is None or getattr(usage, "prompt_tokens", None) is None:
            return
        self._last_usage = {
            "prompt": usage.prompt_tokens,
            "completion": getattr(usage, "completion_tokens", 0) or 0,
            "after_index": snapshot,
        }

    def _mark_usage_upto_appended(self) -> None:
        """Stop double counting the assistant reply generated by this round."""
        if self._last_usage is not None:
            self._last_usage["after_index"] = len(self._messages)

    def _threshold_warning(self) -> ContextWarning | None:
        limit = self.context_window  # 未知窗口时按 128k 默认值告警
        used = self.current_context_tokens()
        if used < limit * self._settings.compact_threshold:
            return None
        self._paused = True
        return ContextWarning(
            used_tokens=used,
            limit_tokens=limit,
            threshold=self._settings.compact_threshold,
        )

    async def compact(
        self,
        user_instruction: str = "",
    ) -> AsyncIterator[AgentEvent]:
        """Manual context compaction (triggered by ``/compact``).

        Order of operations, all orchestrated here without any Function
        Calling tools:

        1. Archive the raw conversation to ``.agents/context/<stamp>.jsonl``
           (must succeed before anything else changes).
        2. Call the LLM once to generate a summary of the conversation.
        3. Replace the live context with system prompt + summary + archive
           note; the registry (tool definitions) is left untouched.
        """

        if self._compacting:
            yield AgentError("上下文压缩已经在进行中。")
            return
        if len(self._messages) <= 1 and not self._has_conversation():
            yield AgentError(
                "当前对话还没有可压缩的内容，先继续对话再使用 /compact。"
            )
            return

        self._compacting = True
        tokens_before = self.current_context_tokens()
        transcript = format_transcript(self._messages)
        try:
            yield CompactionStarted(
                message_count=len(self._messages),
                tokens_before=tokens_before,
            )

            try:
                archive_path = archive_messages(
                    self._settings.workspace_root,
                    self._messages,
                    meta={
                        "model": self._settings.model,
                        "reason": "manual /compact",
                        "tokens_before": tokens_before,
                    },
                )
            except OSError as exc:
                yield CompactionFailed(
                    f"归档保存失败，已取消压缩（上下文保持不变）："
                    f"{type(exc).__name__}: {exc}"
                )
                return
            archive_id = archive_identifier(archive_path)

            summary_messages = self._build_summary_messages(user_instruction)
            try:
                response = await self._client.chat.completions.create(
                    model=self._settings.model,
                    messages=summary_messages,
                    max_tokens=self._settings.compact_summary_tokens + 512,
                )
                summary = (response.choices[0].message.content or "").strip()
            except Exception as exc:  # noqa: BLE001 - surfaced to the front-end
                yield CompactionFailed(
                    f"生成摘要失败，已取消压缩（上下文保持不变，归档文件："
                    f"{archive_id}.jsonl）：{type(exc).__name__}: {exc}"
                )
                return
            if not summary:
                yield CompactionFailed(
                    "模型没有返回摘要内容，已取消压缩（上下文保持不变）。"
                )
                return

            self._replace_with_summary(summary, archive_path)
            tokens_after = self.current_context_tokens()
            yield CompactionCompleted(
                summary=summary,
                archive_id=archive_id,
                archive_path=str(archive_path),
                tokens_before=tokens_before,
                tokens_after=tokens_after,
                transcript=transcript,
            )
        finally:
            self._compacting = False

    def has_conversation(self) -> bool:
        """True once any non-system message exists (usable for /save)."""
        return self._has_conversation()

    def _has_conversation(self) -> bool:
        return any(m.get("role") != "system" for m in self._messages)

    def _build_summary_messages(
        self,
        user_instruction: str,
    ) -> list[dict[str, Any]]:
        transcript = json.dumps(self._messages, ensure_ascii=False, indent=2)
        request = (
            "请压缩以下历史对话。\n\n"
            f"```json\n{transcript}\n```\n\n"
            + (
                f"用户对本次压缩的补充要求：{user_instruction}\n"
                if user_instruction.strip()
                else ""
            )
            + "按照系统提示的结构输出摘要。"
        )
        return [
            {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
            {"role": "user", "content": request},
        ]

    def _replace_with_summary(
        self,
        summary: str,
        archive_path: Path,
    ) -> None:
        archived_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        archive_note = (
            f"\n\n---\n\n此前上下文已于 {archived_at} 完成压缩，"
            f"原始上下文保存在编号为 {archive_identifier(archive_path)} 的"
            f"归档文件中。如需查找历史信息，请使用 recallContext 工具。"
        )
        marker = (
            "此前对话已被压缩。以下摘要包含任务目标、已完成工作、关键信息"
            "和后续计划，请基于它继续任务。\n\n"
        )
        system = dict(self._system_message) if self._system_message else None
        agents = (
            build_agents_md_message(self._agents_md) if self._agents_md else None
        )
        self._messages = (
            ([system] if system else [])
            + ([agents] if agents else [])
            + [{"role": "user", "content": marker + summary + archive_note}]
        )
        self._last_usage = None
        self._paused = False

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
