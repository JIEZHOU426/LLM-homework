"""Message input widget."""

from __future__ import annotations

from textual.widgets import Input


class ChatInput(Input):
    """Single-line input with a qAgent-specific placeholder."""

    def __init__(self) -> None:
        super().__init__(
            placeholder="❯ 输入消息，Enter 发送…",
            id="chat-input",
            select_on_focus=False,
        )
