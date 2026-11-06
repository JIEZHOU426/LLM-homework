"""Modal screens: configuration bootstrap dialog and the session picker."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, OptionList, Static
from textual.widgets.option_list import Option

from core.sessions import SessionSummary


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
    """History session picker: ↑/↓ select, Enter restore, Esc cancel."""

    BINDINGS = [
        Binding("escape", "cancel", "取消", show=True),
        Binding("r", "refresh", "刷新", show=True),
    ]
    AUTO_FOCUS = "#session-list"

    def __init__(self, summaries: list[SessionSummary]) -> None:
        super().__init__()
        self._summaries = summaries
        self._list: OptionList | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="session-panel"):
            yield Static(
                "⧉ 历史会话  ↑↓ 选择 · Enter 恢复 · Esc 取消",
                id="session-panel-title",
            )
            self._list = OptionList(id="session-list")
            yield self._list
            yield Footer()

    def on_mount(self) -> None:
        assert self._list is not None
        if not self._summaries:
            self._list.add_option(
                Option("（暂无历史会话，先 /save 或对话后 /new）", disabled=True)
            )
            return
        for index, summary in enumerate(self._summaries):
            label = (
                f"[b]{escape_markup(summary.title)}[/]\n"
                f"[dim]#{index + 1} · 建立于 {summary.display_created}"
                f" · 更新 {summary.display_updated} · "
                f"{summary.message_count} 条消息 · {summary.path.name}[/]"
            )
            self._list.add_option(Option(label, id=str(summary.path)))

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
        self.dismiss(None)


def escape_markup(text: str) -> str:
    for char in ("[", "]", "\\"):
        text = text.replace(char, f"\\{char}")
    return text
