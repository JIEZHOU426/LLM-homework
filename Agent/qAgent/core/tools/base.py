"""Tool contracts shared by every tool implementation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Mapping


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """Provider-neutral description of a tool."""

    name: str
    description: str
    parameters: Mapping[str, Any]

    def as_openai_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": dict(self.parameters),
            },
        }


class Tool(ABC):
    """A callable capability exposed to the model."""

    @property
    @abstractmethod
    def spec(self) -> ToolSpec:
        """Schema advertised to the model."""

    @abstractmethod
    def run(self, arguments: Mapping[str, Any]) -> str:
        """Execute the tool and return a JSON string."""


ToolHandler = Callable[[Mapping[str, Any]], str]


class FunctionTool(Tool):
    """Adapter that turns a plain function into a :class:`Tool`."""

    def __init__(self, spec: ToolSpec, handler: ToolHandler) -> None:
        self._spec = spec
        self._handler = handler

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    def run(self, arguments: Mapping[str, Any]) -> str:
        return self._handler(arguments)
