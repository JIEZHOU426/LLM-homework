"""Sessions: save → list → load round trip, including the rules-file record."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.sessions import load_session, list_sessions, save_session, session_stamp

MESSAGES = [
    {"role": "system", "content": "系统提示"},
    {"role": "user", "content": "帮我列一下当前目录"},
    {"role": "assistant", "content": "好的", "tool_calls": []},
    {"role": "tool", "tool_call_id": "call_1", "content": "{\"count\": 3}"},
]


class SessionRoundTripTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()
        self.session_id = session_stamp()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_round_trip(self) -> None:
        path = save_session(
            self.root,
            session_id=self.session_id,
            created_at=self.session_id,
            messages=MESSAGES,
            agents_md={"path": "AGENT.md", "content": "始终使用中文"},
            model="deepseek-chat",
        )
        self.assertTrue(path.is_file())

        log = load_session(path)
        self.assertEqual(log.summary.session_id, self.session_id)
        self.assertEqual(log.summary.model, "deepseek-chat")
        self.assertEqual(log.summary.message_count, len(MESSAGES))
        self.assertEqual(log.summary.title, "帮我列一下当前目录")
        self.assertEqual([m["role"] for m in log.messages], ["system", "user", "assistant", "tool"])
        self.assertEqual(log.agents_md["content"], "始终使用中文")

    def test_list_sessions_newest_first(self) -> None:
        first = save_session(
            self.root,
            session_id="20260101-000000",
            created_at="20260101-000000",
            messages=[{"role": "user", "content": "旧会话"}],
        )
        second = save_session(
            self.root,
            session_id="20260102-000000",
            created_at="20260102-000000",
            messages=[{"role": "user", "content": "新会话"}],
        )
        import os
        import time

        os.utime(first, (time.time() - 60, time.time() - 60))
        summaries = list_sessions(self.root)
        self.assertEqual([s.session_id for s in summaries][0], second.stem)

    def test_empty_workspace_lists_nothing(self) -> None:
        self.assertEqual(list_sessions(self.root), [])


if __name__ == "__main__":
    unittest.main()
