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
from textual.containers import Horizontal
from textual.theme import Theme
from textual.widgets import Input

from core import (
    AgentError,
    ChatAgent,
    CompactionCompleted,
    CompactionFailed,
    CompactionStarted,
    ConfigurationError,
    ContextWarning,
    Settings,
    TextDelta,
    ToolCallCompleted,
    ToolCallRequested,
    TurnCompleted,
)
from core.agents_md import agents_md_path, resolve_agents_md_path
from core.sessions import (
    SessionLog,
    SessionSummary,
    list_sessions,
    load_session,
    save_session,
    session_stamp,
)

from .screens import ConfigDialog, SessionListScreen
from .widgets import (
    AppHeader,
    ChatInput,
    ChatView,
    CommandPopup,
    CompactPanel,
    HintBar,
    McpSidebar,
    StatusBar,
)

QAGENT_THEME = Theme(
    name="qagent",
    primary="#f5a623",
    secondary="#58a6ff",
    accent="#f5a623",
    success="#3fb950",
    warning="#d29922",
    error="#f85149",
    foreground="#e6edf3",
    background="#0d1117",
    surface="#161b22",
    panel="#1f242c",
    boost="#2d333b",
    dark=True,
)

WELCOME_TEXT = """\
# ◆ qAgent

**DeepSeek · 终端 AI 助手**

直接输入问题开始对话。Agent 会按需调用工具，并在需要时加载 Skill。
输入 `/` 前缀会弹出命令补全面板。

- `Enter` 发送消息
- `/help` 查看命令
- `/new` 新建会话（自动保存当前会话）
- `/resume` 恢复历史会话
- `/compact` 压缩上下文（上下文达到阈值时需要）
- `Ctrl+Q` 退出
"""

HELP_TEXT = """\
## 命令

| 命令 | 说明 |
| --- | --- |
| `/help` | 显示本帮助 |
| `/new` | 新建会话，当前会话自动保存到事件日志 |
| `/resume` | 历史会话面板：↑↓ 选择、Enter 恢复、Esc 取消 |
| `/save` | 保存当前会话 |
| `/sessions` | 与 `/resume` 相同的历史会话面板 |
| `/clear` | 放弃当前对话内容并开启新会话（不保存） |
| `/compact [备注]` | 压缩上下文：归档原始对话并生成摘要 |
| `/mcp` | 显示 MCP 服务器与可用工具 |
| `/agents` | 查看 AGENTS.md 注入状态 |
| `/context` | 查看上下文用量统计 |
| `/quit`、`/exit` | 退出（自动保存脏会话） |

上下文用量达到阈值时会暂停接受新的提示词，输入 `/compact` 压缩后继续。
压缩摘要缺少细节时可让模型调用 `recallContext` 工具检索历史归档。
快捷键：`Ctrl+Q` 退出，`Ctrl+L` 清空对话。

输入 `/` 时会弹出命令补全面板：`↑↓` 选择，`Tab` 补全，`Esc` 关闭。
"""

# (命令, 说明)。顺序即补全面板中的排序。
COMMANDS: list[tuple[str, str]] = [
    ("/help", "显示帮助"),
    ("/new", "新建会话（自动保存当前会话）"),
    ("/resume", "恢复历史会话"),
    ("/save", "保存当前会话"),
    ("/sessions", "查看历史会话列表"),
    ("/clear", "放弃当前对话（不保存，直接新会话）"),
    ("/compact", "压缩上下文，可附加备注"),
    ("/mcp", "显示 MCP 服务器与工具"),
    ("/agents", "显示 AGENTS.md 注入状态"),
    ("/context", "显示上下文用量"),
    ("/quit", "退出（自动保存）"),
    ("/exit", "退出（自动保存）"),
]


class QAgentApp(App[None]):
    TITLE = "qAgent"
    SUB_TITLE = "DeepSeek · Textual TUI"
    CSS_PATH = Path(__file__).with_name("styles.tcss")

    BINDINGS = [
        Binding("ctrl+q", "quit", "退出"),
        Binding("ctrl+l", "clear_history", "清空对话"),
    ]

    commands = COMMANDS

    def __init__(self, config_created: bool = False) -> None:
        super().__init__()
        self.register_theme(QAGENT_THEME)
        self.theme = "qagent"
        self._agent: ChatAgent | None = None
        self._busy = False
        self._config_created = config_created
        self._settings: Settings | None = None
        self._session_id = session_stamp()
        self._session_created_at = self._session_id

    # ---- layout ------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield AppHeader()
        with Horizontal(id="body"):
            yield ChatView(id="chat")
            yield McpSidebar(id="mcp-sidebar")
        yield StatusBar()
        yield CommandPopup()
        yield ChatInput()
        yield HintBar()

    @property
    def chat(self) -> ChatView:
        return self.query_one(ChatView)

    @property
    def chat_input(self) -> ChatInput:
        return self.query_one(ChatInput)

    @property
    def header(self) -> AppHeader:
        return self.query_one(AppHeader)

    @property
    def status_bar(self) -> StatusBar:
        return self.query_one(StatusBar)

    @property
    def command_popup(self) -> CommandPopup:
        return self.query_one(CommandPopup)

    @property
    def sidebar(self) -> McpSidebar:
        return self.query_one(McpSidebar)

    # ---- startup -----------------------------------------------------------

    async def on_mount(self) -> None:
        self.chat_input.focus()
        self.status_bar.set_workspace(str(Path.cwd()))
        await self.chat.add_message("welcome", WELCOME_TEXT)
        self.sidebar.set_loading()

        try:
            settings = Settings.load()
        except ConfigurationError as exc:
            self._disable_input("配置错误")
            await self.chat.add_message("error", f"配置错误：{exc}")
            return
        self._settings = settings
        self.header.set_model(settings.model)
        self.status_bar.set_workspace(str(settings.workspace_root))

        if self._config_created:
            # 本次启动刚创建了带占位信息的 config.ini。
            self._disable_input("等待配置")
            self.push_screen(
                ConfigDialog(config_path=str(settings.workspace_root / "config.ini"))
            )
            await self.chat.add_message(
                "error",
                "未在当前目录找到 `config.ini`，已自动创建模板并填入占位信息。\n\n"
                f"文件：`{settings.workspace_root / 'config.ini'}`\n\n"
                "请填写 `[LLM] api_key` 等配置，**修改保存后重新启动 "
                "qAgent 才能正常工作。**",
            )
            return

        if not settings.configured:
            self._disable_input("未配置")
            self.header.set_status("error", "配置错误")
            await self.chat.add_message(
                "error",
                "未配置 API Key：请在 `config.ini` 的 `[LLM]` 填写 `api_key`，"
                "或在 `.env` 设置 `DEEPSEEK_API_KEY`，然后重启 qAgent。",
            )
            return

        self._agent = ChatAgent(settings)
        self.status_bar.set_tool_count(self._agent.tool_count)
        self.status_bar.set_skill_count(len(self._agent.skills.skills))
        self._refresh_context_status()
        await self.chat.add_message(
            "system",
            f"`cwd` **{settings.workspace_root}**  ·  "
            f"`model` **{settings.model}**  ·  "
            f"工具 **{self._agent.tool_count}**（MCP 异步加载中）",
        )
        if self._agent.agents_md:
            loaded_path = (
                resolve_agents_md_path(
                    settings.workspace_root, settings.agents_filename
                )
                or agents_md_path(settings.workspace_root, settings.agents_filename)
            )
            await self.chat.add_message(
                "system",
                f"已加载项目约定 **{loaded_path.name}**（一次注入、会话内全程复用，"
                "并持久化到会话事件日志）："
                f"`{loaded_path}`",
            )

        # MCP 异步加载：先进入 TUI，连上后台后动态刷新工具与边栏。
        self.run_worker(self._load_mcp(), group="mcp-loading", exclusive=True)
        self.header.set_status("idle")

    def _disable_input(self, reason: str) -> None:
        self.header.set_status("error", reason)
        self.chat_input.disabled = True

    async def _load_mcp(self) -> None:
        """Async MCP bootstrap: connect servers, then refresh sidebar/counts."""
        agent = self._agent
        if agent is None:
            self.sidebar.set_snapshot([])
            return
        try:
            report = await agent.connect_mcp()
        except Exception as exc:  # noqa: BLE001 - loading must never crash UI
            self.sidebar.set_snapshot(
                [
                    {
                        "name": "mcp-loader",
                        "status": "failed",
                        "tool_count": 0,
                        "tools": [],
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                ]
            )
            return

        self.sidebar.set_snapshot(agent.mcp_snapshot())
        self.status_bar.set_tool_count(agent.tool_count)
        self.header.set_status("idle")
        if report.config_path.exists():
            await self.chat.add_message("system", report.summary())
            await self.chat.add_message(
                "system",
                f"MCP 加载完成，工具数量更新为 **{agent.tool_count}**。"
                "右侧边栏已同步刷新。",
            )

    # ---- input handling ----------------------------------------------------

    async def on_input_changed(self, event: Input.Changed) -> None:
        if event.input is not self.chat_input:
            return
        self.command_popup.update_for(event.value, COMMANDS)

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        event.input.value = ""
        self.command_popup.hide()
        if not text or self._busy:
            return
        if text.startswith("/"):
            await self._handle_command(text)
        else:
            await self._run_turn(text)

    # ---- lifecycle ---------------------------------------------------------

    async def action_quit(self) -> None:
        await self._quit()

    async def on_unmount(self) -> None:
        if self._agent is not None:
            try:
                await self._agent.close_mcp()
            except Exception:  # noqa: BLE001 - shutdown must complete
                pass

    async def _quit(self) -> None:
        if self._agent is not None and self._agent.has_conversation():
            path = self._save_session()
            if path is not None:
                self.notify(f"退出前已自动保存会话：{path.name}", title="会话")
        if self._agent is not None:
            try:
                await self._agent.close_mcp()
            except Exception:  # noqa: BLE001
                pass
            self._agent = None
        self.exit()

    # ---- slash commands ----------------------------------------------------

    async def _handle_command(self, text: str) -> None:
        command, *rest = text.split(maxsplit=1)
        command = command.lower()
        if command in {"/quit", "/exit"}:
            await self._quit()
            return
        if self._agent is None:
            await self.chat.add_message(
                "error", "尚未配置 Agent，命令 无效。请先完成配置并重启。"
            )
            return
        if command == "/new":
            if self._busy:
                self.notify("请等待当前回复结束。", severity="warning")
                return
            await self._new_session(save_current=True)
        elif command == "/clear":
            if self._busy:
                self.notify("请等待当前回复结束。", severity="warning")
                return
            await self._new_session(save_current=False)
        elif command == "/save":
            self._save_session(with_message=True)
        elif command in {"/resume", "/sessions"}:
            if self._busy:
                self.notify(
                    "请等待当前任务结束再切换会话。", severity="warning"
                )
                return
            self.run_worker(self._resume_flow(), group="command")
        elif command == "/compact":
            if self._busy:
                self.notify(
                    "请等待当前任务结束再压缩上下文。", severity="warning"
                )
                return
            if self._agent is not None and self._agent.is_compacting:
                self.notify("上下文压缩正在进行中。", severity="warning")
                return
            self.run_worker(
                self._run_compaction(rest[0].strip() if rest else ""),
                group="turn",
            )
        elif command == "/mcp":
            await self.chat.add_message(
                "system",
                _render_mcp_markdown(self._agent.mcp_snapshot()),
            )
        elif command == "/agents":
            await self._show_agents_status()
        elif command == "/context":
            await self._show_context_info()
        elif command in {"/help", "/?"}:
            await self.chat.add_message("system", HELP_TEXT)
        else:
            suggestion = _closest_command(command)
            await self.chat.add_message(
                "error",
                f"未知命令：`{command}`。输入 `/help` 查看可用命令。"
                + (f" 你是否想输入 `{suggestion}`？" if suggestion else ""),
            )
        self.chat_input.focus()

    # ---- session management ------------------------------------------------

    def _save_session(self, *, with_message: bool = False) -> Path | None:
        agent = self._agent
        settings = self._settings
        if agent is None or settings is None:
            return None
        if not agent.has_conversation():
            if with_message:
                self.notify("当前会话暂无可保存的内容。", severity="warning")
            return None
        agents_md = agent.agents_md
        path = save_session(
            settings.workspace_root,
            session_id=self._session_id,
            created_at=self._session_created_at,
            messages=list(agent.messages),
            agents_md=(
                {
                    "path": settings.agents_filename,
                    "content": agents_md,
                }
                if agents_md
                else None
            ),
            model=settings.model,
        )
        if with_message:
            self.notify(f"会话已保存：`{path.name}`", severity="information")
            self.header.set_status("idle")
        return path

    async def _new_session(self, *, save_current: bool) -> None:
        agent = self._agent
        if agent is not None and save_current and agent.has_conversation():
            path = self._save_session()
            if path is not None:
                await self.chat.add_message(
                    "system",
                    f"当前会话已自动保存：`{path.name}`",
                )
        self._session_id = session_stamp()
        self._session_created_at = self._session_id
        if agent is not None:
            agent.clear()
        await self.chat.clear_messages()
        await self.chat.add_message("welcome", WELCOME_TEXT)
        if agent is not None and agent.agents_md:
            await self.chat.add_message(
                "system",
                f"已重新注入项目约定 **{self._settings.agents_filename}**"
                "（会话内全程复用）。",
            )
        await self.chat.add_message(
            "system",
            f"已开启新会话 `{self._session_id}`，可以开始提问。"
            + ("当前会话未保存。" if not save_current else ""),
        )
        self._refresh_context_status()

    async def _resume_flow(self) -> None:
        """Open the session picker overlay and restore the chosen session."""

        self.chat_input.focus()
        summaries = list_sessions(self._settings.workspace_root)
        summary = await self.push_screen_wait(
            SessionListScreen(summaries, self._settings.workspace_root)
        )
        if summary is None:
            self.chat_input.focus()
            return
        await self._restore_session(summary)

    async def _restore_session(self, summary: SessionSummary) -> None:
        agent = self._agent
        if agent is None:
            return
        try:
            log: SessionLog = load_session(summary.path)
        except Exception as exc:  # noqa: BLE001
            await self.chat.add_message(
                "error", f"读取会话文件失败：{type(exc).__name__}: {exc}"
            )
            return
        if not log.messages:
            await self.chat.add_message(
                "error", f"会话 `{summary.path.name}` 没有可恢复的消息。"
            )
            return

        agents_md_content = (log.agents_md or {}).get("content", "")
        agent.restore(agents_md=agents_md_content, messages=log.messages)
        self._session_id = log.summary.session_id or session_stamp()
        self._session_created_at = log.summary.created_at or self._session_id

        await self.chat.clear_messages()
        await self.chat.add_message("welcome", WELCOME_TEXT)
        await self.chat.add_message(
            "system",
            f"已恢复会话 **{log.summary.title}** "
            f"（{len(log.messages)} 条消息，文件 `{summary.path.name}`）。"
            f"MCP 工具 {agent.tool_count} 个继续可用，输入 /help 查看命令。",
        )
        shown = 0
        for message in log.messages:
            role = message.get("role")
            content = message.get("content") or ""
            if role == "user":
                await self.chat.add_message("user", str(content))
                shown += 1
            elif role == "assistant" and content:
                await self.chat.add_message("assistant", str(content))
                shown += 1
            elif role == "tool":
                await self.chat.add_message(
                    "tool", "（工具调用结果，从会话事件日志恢复）"
                )
                shown += 1
        self._refresh_context_status()

    # ---- informational commands -------------------------------------------

    async def _show_agents_status(self) -> None:
        agent = self._agent
        settings = self._settings
        name = settings.agents_filename
        path = resolve_agents_md_path(
            settings.workspace_root, name
        ) or agents_md_path(settings.workspace_root, name)
        content = agent.agents_md if agent else ""
        if content:
            message = (
                f"### {path.name}\n\n"
                f"- 状态：**已注入**（一次注入，会话内全程复用）\n"
                f"- 文件：`{path}`\n"
                f"- 字符数：{len(content)}\n"
                f"- 压缩后自动重新注入，`/save`/`/new` 时持久化到会话事件日志\n\n"
                "<details><summary>内容预览</summary>\n\n"
                f"{content[:800]}\n</details>"
            )
        elif path.exists():
            message = (
                f"### {path.name}\n\n文件存在（`{path}`）但本会话未注入，"
                "重启或 `/new` 后生效。"
            )
        else:
            message = (
                f"### {path.name}\n\n"
                f"当前目录未找到 `{path}`。创建该文件后，新会话启动时会将"
                "其内容一次性注入聊天历史并持久化到会话事件日志。"
                "（文件名可在 `[agents] filename` 或环境变量 "
                "`QAGENT_AGENTS_FILE` 中改，`AGENT.md` 与 `AGENTS.md` 互为等价名）"
            )
        await self.chat.add_message("system", message)

    async def _show_context_info(self) -> None:
        agent = self._agent
        if agent is None:
            return
        info = agent.context_info()
        paused = info["paused"]
        await self.chat.add_message(
            "system",
            "### 上下文用量\n\n"
            f"- 已使用：**{_format_k(info['used'])}** tokens\n"
            f"- 窗口：**{_format_k(info['limit'])}** tokens"
            + ("（默认）" if info["default"] else "")
            + f"\n- 使用率：**{round(info['ratio'] * 100)}%**\n"
            f"- 压缩阈值：{round(info['threshold'] * 100)}%\n"
            f"- 会话：`{self._session_id}`\n"
            f"- 当前状态：{'已暂停 · 等待 /compact' if paused else '正常接受输入'}",
        )

    # ---- turn loop ---------------------------------------------------------

    async def _run_turn(self, text: str) -> None:
        agent = self._agent
        if agent is None:
            await self.chat.add_message("error", "尚未配置 Agent，无法发送消息。")
            return

        self._busy = True
        self.chat_input.disabled = True
        self.header.set_status("busy")

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
                    self.header.set_status(
                        "tool", f"执行工具 {event.call.name}"
                    )
                elif isinstance(event, ToolCallCompleted):
                    await self.chat.add_message(
                        "tool",
                        _format_tool_event(
                            event, self._settings.tool_result_max_chars
                        ),
                    )
                    self.header.set_status("busy", "继续思考")
                elif isinstance(event, TurnCompleted):
                    if assistant_card is None and event.content:
                        await self.chat.add_message(
                            "assistant", event.content
                        )
                    self._check_context_threshold()
                elif isinstance(event, ContextWarning):
                    await self.chat.add_message(
                        "error",
                        "⚠ 上下文使用量已达 "
                        f"{round(event.threshold * 100)}%"
                        f"（{event.used_tokens}/{event.limit_tokens} tokens），"
                        "已暂停接受新的提示词。请输入 `/compact` 压缩上下文"
                        "（原始对话会先归档到 `.agents/context/`）。",
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
                self.header.set_status("error", "请求失败")
                self._refresh_context_status(status=False)
            else:
                self._refresh_context_status()

    def _check_context_threshold(self) -> None:
        agent = self._agent
        if agent is not None and agent.is_paused:
            self.header.set_status("warning", "上下文告急 · /compact")

    async def _run_compaction(self, instruction: str = "") -> None:
        """Run the manual /compact flow; only the summary LLM call runs."""
        agent = self._agent
        if agent is None:
            await self.chat.add_message(
                "error", "尚未配置 Agent，无法执行 /compact。"
            )
            return

        self._busy = True
        self.chat_input.disabled = True
        self.header.set_status("compact", "压缩上下文")

        try:
            async for event in agent.compact(instruction):
                if isinstance(event, CompactionStarted):
                    await self.chat.add_message(
                        "system",
                        f"开始压缩上下文：{event.message_count} 条消息、"
                        f"{event.tokens_before} tokens。"
                        "流程：归档原始对话 → 生成摘要 → 替换上下文。",
                    )
                elif isinstance(event, CompactionCompleted):
                    await self.chat.add_message(
                        "system",
                        f"原始对话已归档：`{event.archive_path}`\n\n"

                        f"上下文 tokens：**{event.tokens_before} → "
                        f"{event.tokens_after}**",
                    )
                    await self.chat.add_message(
                        "assistant", f"### 上下文摘要\n\n{event.summary}"
                    )
                    self.push_screen(
                        CompactPanel(
                            event.transcript,
                            event.summary,
                            event.archive_id,
                            event.archive_path,
                        )
                    )
                elif isinstance(event, CompactionFailed):
                    await self.chat.add_message("error", event.message)
        except Exception as exc:  # noqa: BLE001 - last-resort UI guard
            await self.chat.add_message(
                "error", f"未处理的错误：{type(exc).__name__}: {exc}"
            )
        finally:
            self._busy = False
            self.chat_input.disabled = False
            self.chat_input.focus()
            self._refresh_context_status()

    def _refresh_context_status(self, *, status: bool = True) -> None:
        """Update the top-bar token gauge and (optionally) the status label."""
        agent = self._agent
        if agent is None:
            return
        info = agent.context_info()
        warn = info["paused"] or info["ratio"] >= agent.compact_threshold
        usage_text = ""
        if info["used"] > 0:
            usage_text = (
                f"上下文 {_format_k(info['used'])} / {_format_k(info['limit'])}"
                + ("（默认）" if info["default"] else "")
                + f" · {round(info['ratio'] * 100)}%"
            )
        self.header.set_usage(usage_text, warn)
        if not status:
            return
        if info["paused"]:
            self.header.set_status("warning", "已暂停 · 输入 /compact 继续")
        else:
            self.header.set_status("idle")


# ---- module-level helpers --------------------------------------------------


def _format_k(tokens: int) -> str:
    """Format token counts as ``64k`` / ``12.5k`` style."""
    value = tokens / 1024
    text = f"{value:.1f}".rstrip("0").rstrip(".")
    return f"{text}k"


def _format_tool_event(event: ToolCallCompleted, limit: int) -> str:
    arguments = _pretty_json(event.call.arguments)
    result = _truncate(event.result, limit)
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
    if limit <= 0 or len(text) <= limit:
        return text
    return f"{text[:limit]}\n…（已截断，共 {len(text)} 字符）"


def _closest_command(command: str) -> str | None:
    needle = command.lower()
    for name, _ in COMMANDS:
        if name.startswith(needle) or needle[1:] in name:
            return name
    return None


def _render_mcp_markdown(snapshot: list[dict]) -> str:
    from .widgets.sidebar import render_snapshot

    return f"### MCP 服务器\n\n{render_snapshot(snapshot)}"
