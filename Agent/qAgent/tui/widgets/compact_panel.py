"""Compaction result panel.

A full-screen view pushed after a successful ``/compact``. Left column: the
original conversation that was archived. Right column: the generated summary.
Either side scrolls independently; ``Esc`` or the close button dismisses it.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Markdown, Static


class CompactPanel(Screen[None]):
    BINDINGS = [("escape", "close_panel", "关闭")]

    def __init__(
        self,
        before_text: str,
        summary: str,
        archive_id: str,
        archive_path: str,
    ) -> None:
        super().__init__()
        self._before_text = before_text
        self._summary = summary
        self._archive_id = archive_id
        self._archive_path = archive_path

    def compose(self) -> ComposeResult:
        yield Static(
            f"❉ 上下文压缩完成 · 归档编号 {self._archive_id}"
            f" · 关闭后可继续输入，历史细节可用 recallContext 检索",
            id="cp-header",
        )
        with Horizontal(id="cp-columns"):
            with VerticalScroll(id="cp-left"):
                yield Markdown(self._before_text, id="cp-left-body")
            with VerticalScroll(id="cp-right"):
                yield Markdown(self._summary, id="cp-right-body")
        with Horizontal(id="cp-footer"):
            yield Button("关闭 (Esc)", variant="primary", id="cp-close")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cp-close":
            self.app.pop_screen()

    def action_close_panel(self) -> None:
        self.app.pop_screen()
