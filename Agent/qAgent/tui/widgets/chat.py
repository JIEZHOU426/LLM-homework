"""Chat transcript widgets."""

from __future__ import annotations

from textual.containers import ScrollableContainer, Vertical
from textual.widgets import Markdown, Static

ROLE_LABELS = {
    "user": "你",
    "assistant": "qAgent",
    "tool": "工具",
    "system": "系统",
    "error": "错误",
}


class MessageCard(Vertical):
    """One message bubble with a role label and Markdown body."""

    def __init__(self, role: str, content: str = "") -> None:
        super().__init__(classes=f"message message-{role}")
        self.role = role
        self._content = content
        self._title = Static(
            ROLE_LABELS.get(role, role.upper()),
            classes="message-role",
        )
        self._body = Markdown(content, classes="message-body")

    def compose(self):
        yield self._title
        yield self._body

    async def append_text(self, text: str) -> None:
        self._content += text
        await self._body.update(self._content)

    async def set_text(self, text: str) -> None:
        self._content = text
        await self._body.update(self._content)


class ChatView(ScrollableContainer):
    """Scrollable transcript; the only widget the app writes messages into."""

    can_focus = False

    async def add_message(self, role: str, content: str = "") -> MessageCard:
        card = MessageCard(role, content)
        await self.mount(card)
        self.scroll_to_bottom()
        return card

    async def clear_messages(self) -> None:
        await self.remove_children()

    def scroll_to_bottom(self) -> None:
        self.scroll_end(animate=False)
