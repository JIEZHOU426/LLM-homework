"""Conversation loop guard: the per-turn tool-step cap really stops a loop."""

from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from core.agent import ChatAgent
from core.config import Settings


class _FakeStream:
    """Async stream that always asks for one tool call and never answers."""

    def __init__(self) -> None:
        self._sent = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._sent:
            raise StopAsyncIteration
        self._sent = True
        delta = SimpleNamespace(
            content=None,
            tool_calls=[
                SimpleNamespace(
                    index=0,
                    id="call_1",
                    type="function",
                    function=SimpleNamespace(name="get_cwd", arguments="{}"),
                )
            ],
        )
        chunk = SimpleNamespace(
            choices=[SimpleNamespace(delta=delta)],
            usage=None,
        )
        return chunk


class _FakeCompletions:
    async def create(self, **kwargs):  # noqa: ANN003 - mirrors the SDK signature
        return _FakeStream()


class _FakeClient:
    def __init__(self) -> None:
        self.chat = SimpleNamespace(completions=_FakeCompletions())


class TurnGuardTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def make_agent(self, max_steps: int) -> ChatAgent:
        settings = Settings(
            api_key="test-key",
            workspace_root=self.root,
            project_root=self.root,
            max_steps=max_steps,
            confine_paths=False,
        )
        return ChatAgent(settings, client=_FakeClient())

    def test_step_cap_stops_the_loop(self) -> None:
        agent = self.make_agent(max_steps=3)
        events = asyncio.run(self._collect(agent))
        messages = [event.message for event in events if hasattr(event, "message")]
        self.assertTrue(
            any("上限" in text for text in messages),
            f"未触发步数上限：{messages}",
        )
        # 已执行过的工具结果确实回填进了历史
        roles = [m["role"] for m in agent.messages]
        self.assertIn("tool", roles)
        self.assertLessEqual(roles.count("tool"), 3)

    async def _collect(self, agent: ChatAgent):
        return [event async for event in agent.send("一直调用工具")]


if __name__ == "__main__":
    unittest.main()
