"""Status bar widget."""

from __future__ import annotations

from textual.widgets import Static

STATUS_COLORS = {
    "idle": "green",
    "busy": "yellow",
    "tool": "cyan",
    "error": "red",
}


class StatusBar(Static):
    def __init__(self, model: str) -> None:
        super().__init__(id="status-bar")
        self._model = model
        self._state = "idle"
        self._detail = "就绪"

    def set_model(self, model: str) -> None:
        self._model = model
        self._refresh_display()

    def set_status(self, state: str, detail: str = "") -> None:
        self._state = state
        self._detail = detail or {
            "idle": "就绪",
            "busy": "思考中",
            "tool": "执行工具",
            "error": "出错",
        }.get(state, state)
        self._refresh_display()

    def _refresh_display(self) -> None:
        color = STATUS_COLORS.get(self._state, "white")
        self.update(
            f"[{color}]● {self._detail}[/]  "
            f"[dim]{self._model}[/dim]"
        )
