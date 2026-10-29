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
    "ConfigurationError",
    "Settings",
    "TextDelta",
    "ToolCall",
    "ToolCallCompleted",
    "ToolCallRequested",
    "TurnCompleted",
]
