"""Events emitted by the conversation loop.

Front-ends consume this event stream and translate it into their own
presentation model (Textual widgets, SSE frames, Qt signals, ...). The core
never knows which front-end is listening.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Union


@dataclass(frozen=True, slots=True)
class ToolCall:
    """A fully accumulated tool call emitted by the model."""

    id: str
    name: str
    arguments: str


@dataclass(frozen=True, slots=True)
class TextDelta:
    """An incremental piece of assistant text."""

    text: str


@dataclass(frozen=True, slots=True)
class ToolCallRequested:
    """The model requested a tool call; execution is about to start."""

    call: ToolCall


@dataclass(frozen=True, slots=True)
class ToolCallCompleted:
    """A tool call finished and returned a JSON string."""

    call: ToolCall
    result: str


@dataclass(frozen=True, slots=True)
class TurnCompleted:
    """The assistant finished a full turn (including any tool round-trips)."""

    content: str


@dataclass(frozen=True, slots=True)
class AgentError:
    """A recoverable error surfaced to the front-end."""

    message: str


@dataclass(frozen=True, slots=True)
class ContextWarning:
    """Context usage crossed the compaction threshold."""

    used_tokens: int
    limit_tokens: int
    threshold: float


@dataclass(frozen=True, slots=True)
class CompactionStarted:
    """A manual /compact started; only the summary LLM call may run now."""

    message_count: int
    tokens_before: int


@dataclass(frozen=True, slots=True)
class CompactionCompleted:
    """Compaction finished; the raw conversation was archived and replaced."""

    summary: str
    archive_id: str
    archive_path: str
    tokens_before: int
    tokens_after: int
    transcript: str  # 压缩前的原始会话，供 TUI 双栏面板展示


@dataclass(frozen=True, slots=True)
class CompactionFailed:
    """Compaction aborted; the conversation was left unchanged."""

    message: str


AgentEvent = Union[
    TextDelta,
    ToolCallRequested,
    ToolCallCompleted,
    TurnCompleted,
    AgentError,
    ContextWarning,
    CompactionStarted,
    CompactionCompleted,
    CompactionFailed,
]
