"""Session information bar."""

from __future__ import annotations

from rich.markup import escape
from textual.widgets import Static


class StatusBar(Static):
    """Shows the working directory and how many tools/skills are available."""

    def __init__(self) -> None:
        super().__init__(id="status-bar")
        self._workspace = ""
        self._tool_count: int | None = None
        self._skill_count: int | None = None
        self._refresh_display()

    def set_workspace(self, workspace: str) -> None:
        self._workspace = workspace
        self._refresh_display()

    def set_tool_count(self, count: int) -> None:
        self._tool_count = count
        self._refresh_display()

    def set_skill_count(self, count: int) -> None:
        self._skill_count = count
        self._refresh_display()

    def _refresh_display(self) -> None:
        parts = []
        if self._workspace:
            parts.append(
                f"[#8b949e]cwd[/] [#e6edf3]{escape(self._workspace)}[/]"
            )
        if self._tool_count is not None:
            parts.append(
                f"[#8b949e]tools[/] [#e6edf3]{self._tool_count}[/]"
            )
        if self._skill_count is not None:
            parts.append(
                f"[#8b949e]skills[/] [#e6edf3]{self._skill_count}[/]"
            )
        if not parts:
            parts.append("[#8b949e]正在初始化…[/]")
        self.update("   ".join(parts))
