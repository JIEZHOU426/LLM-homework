"""Modal screens: configuration bootstrap dialog and the session picker."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, OptionList, Static
from textual.widgets.option_list import Option

from core.sessions import SessionSummary, list_sessions


class ConfigDialog(ModalScreen[None]):
    """Shown when a fresh ``config.ini`` was bootstrapped at startup."""

    BINDINGS = [
        Binding("escape", "dismiss", "关闭", show=True),
        Binding("enter", "dismiss", "我知道了", show=True),
    ]

    def __init__(self, config_path: str, hint: str = "") -> None:
        super().__init__()
        self._config_path = config_path
        self._hint = hint

    def compose(self) -> ComposeResult:
        with Vertical(id="config-dialog"):
            yield Static(
                "◆ 已生成 config.ini 配置文件", id="config-dialog-title"
            )
            yield Static(
                f"未在当前目录找到 `config.ini`，已创建带占位信息的模板：\n\n"
                f"`{self._config_path}`\n\n"
                "请填写 `[LLM] api_key`（以及需要修改的 base_url / model），\n"
                "**修改保存后重新启动 qAgent 才能正常工作。**\n"
                + (f"\n{self._hint}\n" if self._hint else ""),
                classes="config-dialog-body",
            )
            with Horizontal(id="config-dialog-buttons"):
                yield Button("我知道了", variant="warning", id="config-dialog-ok")
            yield Static("[dim]Esc / Enter 关闭[/]", id="config-dialog-hint")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss()

    def action_dismiss(self, _result=None) -> None:
        self.dismiss()


class SessionListScreen(ModalScreen[SessionSummary | None]):
    """History session picker: ↑/↓ select, Enter restore, Esc cancel, r reload."""

    BINDINGS = [
        Binding("escape", "cancel", "取消", show=True),
        Binding("r", "refresh", "刷新", show=True),
    ]
    AUTO_FOCUS = "#session-list"

    def __init__(
        self,
        summaries: list[SessionSummary],
        workspace_root: Path | None = None,
    ) -> None:
        super().__init__()
        self._summaries = list(summaries)
        self._workspace_root = workspace_root
        self._list: OptionList | None = None
        self._notice: Static | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="session-panel"):
            yield Static(
                "⧉ 历史会话  ↑↓ 选择 · Enter 恢复 · Esc 取消 · r 刷新",
                id="session-panel-title",
            )
            self._list = OptionList(id="session-list")
            yield self._list
            self._notice = Static("", id="session-panel-notice")
            yield self._notice
            yield Footer()

    def on_mount(self) -> None:
        self._populate()

    def _populate(self, notice: str = "") -> None:
        assert self._list is not None
        self._list.clear_options()
        if not self._summaries:
            self._list.add_option(
                Option("（暂无历史会话，先 /save 或对话后 /new）", disabled=True)
            )
        else:
            for index, summary in enumerate(self._summaries):
                label = (
                    f"[b]{escape_markup(summary.title)}[/]\n"
                    f"[dim]#{index + 1} · 建立于 {summary.display_created}"
                    f" · 更新 {summary.display_updated} · "
                    f"{summary.message_count} 条消息 · {summary.path.name}[/]"
                )
                self._list.add_option(Option(label, id=str(summary.path)))
            self._list.highlighted = 0
        if self._notice is not None:
            self._notice.update(notice)

    def on_option_list_option_selected(
        self,
        event: OptionList.OptionSelected,
    ) -> None:
        assert self._list is not None
        option = event.option
        for summary in self._summaries:
            if str(summary.path) == option.id:
                self.dismiss(summary)
                return
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_refresh(self) -> None:
        """Re-scan the sessions directory and rebuild the list in place."""

        if self._workspace_root is None:
            self._populate("（未绑定工作目录，无法刷新）")
            return
        self._summaries = list_sessions(self._workspace_root)
        self._populate(f"已刷新：共 {len(self._summaries)} 个会话")


def escape_markup(text: str) -> str:
    for char in ("[", "]", "\\"):
        text = text.replace(char, f"\\{char}")
    return text
