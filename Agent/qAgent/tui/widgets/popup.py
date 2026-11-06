"""Slash-command completion popup shown above the chat input."""

from __future__ import annotations

from textual.containers import Vertical
from textual.widgets import Static

MAX_VISIBLE_ROWS = 8


class CommandPopup(Vertical):
    """Filtered list of slash commands; driven by the app + ChatInput."""

    def __init__(self) -> None:
        super().__init__(id="command-popup")
        self._options: list[tuple[str, str]] = []
        self._selected = 0
        self._visible = False
        self._count_line = Static("", id="popup-count")

    @property
    def visible_options(self) -> list[tuple[str, str]]:
        return self._options

    @property
    def is_visible(self) -> bool:
        return self._visible

    @property
    def selected_index(self) -> int:
        return self._selected

    @property
    def selected_command(self) -> str | None:
        if self._visible and self._options:
            return self._options[self._selected][0]
        return None

    def update_for(self, text: str, commands: list[tuple[str, str]]) -> None:
        """Refresh matches for the typed value and show/hide accordingly."""

        text = text.strip()
        if not text.startswith("/") or " " in text or len(commands) == 0:
            self.hide()
            return

        needle = text.lower()
        matches = [
            (cmd, desc)
            for cmd, desc in commands
            if cmd.lower().startswith(needle)
        ]
        if not matches and needle:
            # Fall back to substring matching so `/ctx` finds /context.
            matches = [
                (cmd, desc)
                for cmd, desc in commands
                if needle[1:] in cmd.lower()
            ]
        if not matches:
            self.hide()
            return
        exact = [entry for entry in matches if entry[0].lower() == needle]
        if exact:
            self.hide()
            return
        self.show_matches(matches)

    def show_matches(self, matches: list[tuple[str, str]]) -> None:
        self._options = matches
        self._selected = 0
        self._visible = True
        self.display = True
        self._render_rows()

    def hide(self) -> None:
        self._visible = False
        self._options = []
        self._selected = 0
        self.display = False

    def move_selection(self, delta: int) -> None:
        if not self._visible or not self._options:
            return
        count = min(len(self._options), MAX_VISIBLE_ROWS)
        self._selected = (self._selected + delta) % count
        self._render_rows()

    def render_rows(self) -> None:
        self._render_rows()

    def _render_rows(self) -> None:
        self.remove_children()
        shown = self._options[:MAX_VISIBLE_ROWS]
        for index, (command, description) in enumerate(shown):
            classes = "popup-option"
            if index == self._selected:
                classes += " selected"
            self.mount(
                Static(
                    f"[b {self._command_color(index)}]{command}[/]"
                    f"  [dim]{description}[/]",
                    classes=classes,
                )
            )
        hidden = len(self._options) - len(shown)
        if hidden > 0:
            self._count_line.display = True
            self._count_line.update(
                f"[dim]… 还有 {hidden} 个命令，继续输入过滤[/]"
            )
            self.mount(self._count_line)

    def _command_color(self, index: int) -> str:
        return "#f5a623" if index == self._selected else "#e6edf3"
