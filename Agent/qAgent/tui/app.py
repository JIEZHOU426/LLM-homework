"""Textual application.

This module is the composition root for the TUI. It translates core events
into widgets. All business logic lives in ``core``; adding a web or desktop UI
means writing a new composition root that consumes the same event stream.
"""

from __future__ import annotations

import json
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, Input

from core import (
    AgentError,
    ChatAgent,
    ConfigurationError,
    Settings,
    TextDelta,
    ToolCallCompleted,
    ToolCallRequested,
    TurnCompleted,
)

from .widgets import ChatInput, ChatView, StatusBar

WELCOME_TEXT = """\
# qAgent

基于 DeepSeek 的命令行聊天 Agent，当前使用 Textual TUI。

- 直接输入问题，按 **Enter** 发送
- Agent 会按需调用工具（时间、文件操作、网页抓取、联网搜索）
- 输入 `/help` 查看命令，`Ctrl+Q` 退出
"""

HELP_TEXT = """\
## 命令

| 命令 | 说明 |
| --- | --- |
| `/help` | 显示帮助 |
| `/clear` 或 `/new` | 清空对话历史 |
| `/quit` 或 `/exit` | 退出程序 |

快捷键：`Ctrl+Q` 退出，`Ctrl+L` 清空对话。
"""


class QAgentApp(App[None]):
    TITLE = "qAgent"
    SUB_TITLE = "DeepSeek · Textual TUI"
    CSS_PATH = Path(__file__).with_name("styles.tcss")

    BINDINGS = [
        Binding("ctrl+q", "quit", "退出"),
        Binding("ctrl+l", "clear_history", "清空对话"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._agent: ChatAgent | None = None
        self._busy = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield ChatView(id="chat")
        yield StatusBar("未连接")
        yield ChatInput()
        yield Footer()

    @property
    def chat(self) -> ChatView:
        return self.query_one(ChatView)

    @property
    def chat_input(self) -> ChatInput:
        return self.query_one(ChatInput)

    @property
    def status_bar(self) -> StatusBar:
        return self.query_one(StatusBar)

    async def on_mount(self) -> None:
        self.chat_input.focus()
        await self.chat.add_message("system", WELCOME_TEXT)

        try:
            settings = Settings.load()
        except ConfigurationError as exc:
            self.status_bar.set_status("error", "配置错误")
            await self.chat.add_message("error", f"配置错误：{exc}")
            self.chat_input.disabled = True
            return

        self.status_bar.set_model(settings.model)
        self._agent = ChatAgent(settings)
        self.status_bar.set_status("idle")

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        event.input.value = ""
        if not text or self._busy:
            return
        if text.startswith("/"):
            await self._handle_command(text)
        else:
            await self._run_turn(text)

    async def _handle_command(self, text: str) -> None:
        command = text.split(maxsplit=1)[0].lower()
        if command in {"/quit", "/exit"}:
            self.exit()
        elif command in {"/clear", "/new"}:
            if self._busy:
                self.notify("请等待当前回复结束。", severity="warning")
                return
            await self._clear_conversation()
        elif command in {"/help", "/?"}:
            await self.chat.add_message("system", HELP_TEXT)
        else:
            await self.chat.add_message(
                "error",
                f"未知命令：`{command}`。输入 `/help` 查看可用命令。",
            )

    async def _run_turn(self, text: str) -> None:
        agent = self._agent
        if agent is None:
            await self.chat.add_message("error", "尚未配置 Agent，无法发送消息。")
            return

        self._busy = True
        self.chat_input.disabled = True
        self.status_bar.set_status("busy")

        assistant_card = None
        assistant_text = ""
        failed = False

        try:
            async for event in agent.send(text):
                if isinstance(event, TextDelta):
                    if assistant_card is None:
                        assistant_card = await self.chat.add_message(
                            "assistant", ""
                        )
                    assistant_text += event.text
                    await assistant_card.append_text(event.text)
                    self.chat.scroll_to_bottom()
                elif isinstance(event, ToolCallRequested):
                    self.status_bar.set_status(
                        "tool", f"执行工具 {event.call.name}"
                    )
                elif isinstance(event, ToolCallCompleted):
                    await self.chat.add_message(
                        "tool", _format_tool_event(event)
                    )
                    self.status_bar.set_status("busy", "继续思考")
                elif isinstance(event, TurnCompleted):
                    if assistant_card is None and event.content:
                        await self.chat.add_message(
                            "assistant", event.content
                        )
                elif isinstance(event, AgentError):
                    failed = True
                    await self.chat.add_message("error", event.message)
        except Exception as exc:  # noqa: BLE001 - last-resort UI guard
            failed = True
            await self.chat.add_message(
                "error", f"未处理的错误：{type(exc).__name__}: {exc}"
            )
        finally:
            self._busy = False
            self.chat_input.disabled = False
            self.chat_input.focus()
            if failed:
                self.status_bar.set_status("error", "请求失败")
            else:
                self.status_bar.set_status("idle")

    async def _clear_conversation(self) -> None:
        if self._agent is not None:
            self._agent.clear()
        await self.chat.clear_messages()
        await self.chat.add_message("system", "对话已清空，可以开始新的提问。")

    def action_clear_history(self) -> None:
        if self._busy:
            self.notify("请等待当前回复结束。", severity="warning")
            return
        self.run_worker(self._clear_conversation(), group="command")


def _format_tool_event(event: ToolCallCompleted) -> str:
    arguments = _pretty_json(event.call.arguments)
    result = _truncate(event.result, 4000)
    return (
        f"### 调用 `{event.call.name}`\n\n"
        f"**参数**\n\n~~~json\n{arguments}\n~~~\n\n"
        f"**结果**\n\n~~~text\n{result}\n~~~"
    )


def _pretty_json(raw: str) -> str:
    try:
        return json.dumps(json.loads(raw), ensure_ascii=False, indent=2)
    except (json.JSONDecodeError, TypeError):
        return raw


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit]}\n…（已截断，共 {len(text)} 字符）"
