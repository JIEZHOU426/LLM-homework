"""Tool-call journal: one JSONL line per call, with duration and error code."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from core.call_log import ToolCallLog, log_path
from core.tools.clock import build_clock_tools
from core.tools.registry import ToolRegistry


class ToolCallLogTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()
        self.log = ToolCallLog(self.root)
        self.registry = ToolRegistry(build_clock_tools(), tool_log=self.log)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def records(self) -> list[dict]:
        path = log_path(self.root)
        self.assertTrue(path.is_file(), "日志文件未生成")
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    def test_success_and_failure_are_both_recorded(self) -> None:
        self.registry.execute("isleapyear", json.dumps({"year": 2024}))
        records = self.records()
        self.assertEqual(len(records), 1)
        entry = records[0]
        self.assertEqual(entry["name"], "isleapyear")
        self.assertTrue(entry["ok"])
        self.assertIsInstance(entry["dur_ms"], int)
        self.assertEqual(entry["args"], ["year"])
        # 参数值不入日志
        self.assertNotIn("2024", json.dumps(entry))

        self.registry.execute("isleapyear", json.dumps({"year": "bad"}))
        records = self.records()
        self.assertEqual(len(records), 2)
        self.assertFalse(records[1]["ok"])

    def test_unknown_tool_is_logged_with_code(self) -> None:
        self.registry.execute("does-not-exist", "{}")
        entry = self.records()[0]
        self.assertFalse(entry["ok"])
        self.assertEqual(entry["code"], "TOOL_ERROR")

    def test_disabled_log_writes_nothing(self) -> None:
        registry = ToolRegistry(
            build_clock_tools(), tool_log=ToolCallLog(self.root, enabled=False)
        )
        registry.execute("get_cwd", "{}")
        self.assertFalse(log_path(self.root).exists())


if __name__ == "__main__":
    unittest.main()
