"""Bottom keyboard shortcut hints."""

from __future__ import annotations

from textual.widgets import Static


class HintBar(Static):
    def __init__(self) -> None:
        super().__init__(
            "[#8b949e]Enter[/] 发送   "
            "[#8b949e]/[/] 命令补全   "
            "[#8b949e]Tab[/] 补全所选   "
            "[#8b949e]Ctrl+L[/] 清空   "
            "[#8b949e]Ctrl+Q[/] 退出",
            id="hint-bar",
        )
