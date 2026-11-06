"""UI-agnostic core for qAgent.

The core package owns configuration, the LLM client, the tool system and the
conversation loop. It must never import anything from ``tui`` (or any future
front-end package).
"""

from .agent import ChatAgent
from .config import ConfigurationError, Settings
from .events import (
    AgentError,
    AgentEvent,
    CompactionCompleted,
    CompactionFailed,
    CompactionStarted,
    ContextWarning,
    TextDelta,
    ToolCall,
    ToolCallCompleted,
    ToolCallRequested,
    TurnCompleted,
)

__all__ = [
    "AgentError",
    "AgentEvent",
    "ChatAgent",
    "CompactionCompleted",
    "CompactionFailed",
    "CompactionStarted",
    "ConfigurationError",
    "ContextWarning",
    "Settings",
    "TextDelta",
    "ToolCall",
    "ToolCallCompleted",
    "ToolCallRequested",
    "TurnCompleted",
]
