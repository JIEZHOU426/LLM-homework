"""Top application bar."""

from __future__ import annotations

from rich.markup import escape
from textual.containers import Horizontal
from textual.widgets import Static

STATUS_STYLES = {
    "idle": ("#3fb950", "●", "就绪"),
    "busy": ("#d29922", "◐", "思考中"),
    "tool": ("#58a6ff", "⚙", "执行工具"),
    "error": ("#f85149", "✖", "出错"),
}


class AppHeader(Horizontal):
    """Brand, model and live agent status."""

    def __init__(self) -> None:
        super().__init__(id="top-bar")
        self._model = "未连接"
        self._state = "idle"
        self._detail = "就绪"
        self._brand = Static(
            "◆ [b]qAgent[/b]  [dim]DeepSeek · Terminal Agent[/dim]",
            id="brand",
        )
        self._session = Static("", id="session")
        self._refresh_display()

    def compose(self):
        yield self._brand
        yield self._session

    def on_mount(self) -> None:
        self._refresh_display()

    def set_model(self, model: str) -> None:
        self._model = model
        self._refresh_display()

    def set_status(self, state: str, detail: str = "") -> None:
        self._state = state
        self._detail = detail or STATUS_STYLES.get(state, ("", "", state))[2]
        self._refresh_display()

    def _refresh_display(self) -> None:
        color, icon, label = STATUS_STYLES.get(
            self._state,
            ("#8b949e", "●", self._state),
        )
        detail = self._detail or label
        self._session.update(
            f"[{color}]{icon} {escape(detail)}[/]  "
            f"[dim]{escape(self._model)}[/dim]"
        )
