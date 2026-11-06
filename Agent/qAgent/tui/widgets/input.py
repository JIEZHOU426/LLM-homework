"""Message input widget with slash-command popup key handling."""

from __future__ import annotations

from textual.binding import Binding
from textual.widgets import Input


class ChatInput(Input):
    """Single-line input wired to the app-level CommandPopup.

    While the completion popup is visible, Tab completes the highlighted
    command and Up/Down move the highlight; otherwise pressed keys fall
    through to normal input behaviour.
    """

    BINDINGS = [
        Binding("down", "popup_next", show=False),
        Binding("up", "popup_prev", show=False),
        Binding("tab", "popup_complete", show=False),
        Binding("escape", "popup_dismiss", show=False),
    ]

    def __init__(self) -> None:
        super().__init__(
            placeholder="❯ 输入消息或 / 命令，Enter 发送…",
            id="chat-input",
            select_on_focus=False,
        )

    @property
    def popup(self):
        return self.app.command_popup

    def action_popup_next(self) -> None:
        if self.popup.is_visible:
            self.popup.move_selection(1)

    def action_popup_prev(self) -> None:
        if self.popup.is_visible:
            self.popup.move_selection(-1)

    def action_popup_dismiss(self) -> None:
        if self.popup.is_visible:
            self.popup.hide()

    def action_popup_complete(self) -> None:
        popup = self.popup
        if not popup.is_visible or popup.selected_command is None:
            return
        self.value = popup.selected_command + " "
        self.cursor_position = len(self.value)
        popup.update_for(self.value, self.app.commands)

    async def action_submit(self) -> None:
        popup = self.popup
        command = popup.selected_command
        text = self.value.strip()
        if (
            popup.is_visible
            and command is not None
            and text
            and text != command
            and text.startswith("/")
            and " " not in text
            and command.lower().startswith(text.lower())
        ):
            # Incomplete command name: Enter completes it instead of
            # submitting an unknown command like "/ne".
            self.value = command + " "
            self.cursor_position = len(self.value)
            popup.update_for(self.value, self.app.commands)
            return
        await super().action_submit()
