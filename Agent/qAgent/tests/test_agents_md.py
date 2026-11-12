"""Project rules file: configured name, alias fallback, one-shot injection."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.agents_md import (
    build_agents_md_message,
    candidate_names,
    read_agents_md,
    resolve_agents_md_path,
)


class AgentsFileTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def write(self, name: str, content: str) -> None:
        (self.root / name).write_text(content, encoding="utf-8")

    def test_missing_file_returns_empty_string(self) -> None:
        self.assertEqual(read_agents_md(self.root), "")
        self.assertIsNone(resolve_agents_md_path(self.root))

    def test_agents_md_alias_is_read(self) -> None:
        self.write("AGENTS.md", "使用中文回答")
        self.assertEqual(read_agents_md(self.root), "使用中文回答")
        self.assertEqual(resolve_agents_md_path(self.root).name, "AGENTS.md")

    def test_configured_name_wins_over_alias(self) -> None:
        self.write("AGENT.md", "来自 AGENT.md")
        self.write("AGENTS.md", "来自 AGENTS.md")
        self.assertEqual(read_agents_md(self.root).splitlines()[0], "来自 AGENT.md")
        self.assertEqual(read_agents_md(self.root, "PROJECT_RULES.md"), "")
        self.write("PROJECT_RULES.md", "自定义规则")
        self.assertEqual(read_agents_md(self.root, "PROJECT_RULES.md"), "自定义规则")
        self.assertEqual(read_agents_md(self.root, "PROJECT_RULES.md").strip(), "自定义规则")

    def test_candidate_names_are_deduplicated(self) -> None:
        self.assertEqual(candidate_names("AGENTS.md"), ("AGENTS.md", "AGENT.md"))
        self.assertEqual(candidate_names(None), ("AGENT.md", "AGENTS.md"))

    def test_message_carries_file_name_and_content(self) -> None:
        message = build_agents_md_message("规则正文", "AGENT.md")
        self.assertEqual(message["role"], "system")
        self.assertIn("<AGENT.md>", message["content"])
        self.assertIn("规则正文", message["content"])


if __name__ == "__main__":
    unittest.main()
