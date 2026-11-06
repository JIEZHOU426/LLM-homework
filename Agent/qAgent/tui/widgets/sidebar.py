"""Right-hand sidebar listing connected MCP servers and their tools.

The sidebar is part of the screen layout from the very first frame and shows
a loading state while MCP servers connect asynchronously in a background
worker; once connections resolve the app pushes a snapshot and the panel
re-renders in place without restarting the TUI.
"""

from __future__ import annotations

from textual.containers import Vertical
from textual.widgets import Markdown, Static

LOADING_TEXT = (
    "⏳ **正在异步加载 MCP 服务器…**\n\n"
    "TUI 已就绪，连接完成后此处会自动刷新。"
)
EMPTY_TEXT = (
    "未连接任何 MCP 服务器。\n\n"
    "在项目根目录创建 `.mcp.json` 配置 `mcpServers`，"
    "重启或使用 `/mcp` 查看状态。"
)


def render_snapshot(snapshot: list[dict]) -> str:
    lines: list[str] = []
    connected = 0
    for server in snapshot:
        name = server["name"] or "?"
        status = server["status"]
        if status == "connected":
            connected += 1
            lines.append(f"#### ✅ {name} ({server['tool_count']})")
            for tool in server["tools"]:
                description = tool.get("description") or ""
                lines.append(
                    f"- `{tool['name']}`"
                    + (f" — {description}" if description else "")
                )
        else:
            icon = "❌" if status == "failed" else "○"
            lines.append(f"#### {icon} {name}")
            if server.get("error"):
                lines.append(f"> {status}: {server['error']}")
    if not snapshot:
        return EMPTY_TEXT
    header = f"已连接 {connected} / {len(snapshot)} 台服务器\n\n---\n\n"
    return header + "\n\n".join(lines)


class McpSidebar(Vertical):
    """The ``MCP 服务器`` side panel."""

    can_focus = False

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("id", "mcp-sidebar")
        super().__init__(**kwargs)
        self._loading = Static("MCP 加载中", id="sidebar-title")
        self._body = Markdown(LOADING_TEXT, classes="sidebar-body")

    def compose(self):
        yield self._loading
        yield self._body

    def set_loading(self) -> None:
        self._loading.update("⚙ MCP 服务器 · 加载中")
        self._refresh_body(LOADING_TEXT)

    def set_snapshot(self, snapshot: list[dict]) -> None:
        connected = sum(
            1 for server in snapshot if server["status"] == "connected"
        )
        count = sum(
            server["tool_count"]
            for server in snapshot
            if server["status"] == "connected"
        )
        self._loading.update(
            f"⚙ MCP 服务器 · {connected}/{len(snapshot)}"
            f" · 工具 {count}"
        )
        self._refresh_body(render_snapshot(snapshot))

    def _refresh_body(self, text: str) -> None:
        self.run_worker(
            self._body.update(text),
            name="sidebar-body",
            group="sidebar-body",
            exclusive=True,
        )
