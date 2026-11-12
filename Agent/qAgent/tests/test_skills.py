"""Skill catalog: create / refuse-overwrite / discover / load."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from core.skills import SkillCatalog


class SkillCatalogTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()
        self.catalog = SkillCatalog(self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_create_writes_frontmatter_and_registers(self) -> None:
        raw = self.catalog.create("demo-skill", "# 演示\n\n步骤一：先做这件事。")
        payload = json.loads(raw)
        self.assertNotIn("error", payload)
        skill_file = self.root / ".agents" / "skills" / "demo-skill" / "SKILL.md"
        self.assertTrue(skill_file.is_file())
        text = skill_file.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---"))
        self.assertIn("name:", text)
        self.assertIn("description:", text)
        self.assertEqual(len(self.catalog.skills), 1)

    def test_duplicate_create_is_refused(self) -> None:
        self.catalog.create("demo-skill", "第一版")
        again = json.loads(self.catalog.create("demo-skill", "第二版"))
        self.assertIn("已拒绝覆盖", again["error"])

    def test_empty_context_is_refused(self) -> None:
        self.assertIn("error", json.loads(self.catalog.create("x", "   ")))

    def test_unsafe_name_is_normalised_inside_skills_dir(self) -> None:
        # "../escape" 被规范化为 "escape"，不会写到 skills 目录之外
        payload = json.loads(self.catalog.create("../escape", "body"))
        self.assertNotIn("error", payload)
        target = self.root / ".agents" / "skills" / "escape" / "SKILL.md"
        self.assertTrue(target.is_file())
        self.assertEqual(Path(payload["directory"]).resolve().parent.name, "skills")

    def test_discover_reads_existing_skill(self) -> None:
        directory = self.root / ".agents" / "skills" / "existing"
        directory.mkdir(parents=True)
        (directory / "SKILL.md").write_text(
            "---\nname: existing\ndescription: 已存在的技能\n---\n\n正文\n",
            encoding="utf-8",
        )
        catalog = SkillCatalog.discover(self.root)
        self.assertEqual([s.name for s in catalog.skills], ["existing"])
        self.assertIn("existing", catalog.system_prompt())

    def test_load_returns_body_and_rejects_unknown(self) -> None:
        self.catalog.create("demo-skill", "# 演示\n\n只做一件事。")
        loaded = json.loads(self.catalog.load("demo-skill"))
        self.assertNotIn("error", loaded)
        self.assertIn("只做一件事", json.dumps(loaded, ensure_ascii=False))
        self.assertIn("error", json.loads(self.catalog.load("missing")))

    def test_attachment_cannot_escape_skill_directory(self) -> None:
        self.catalog.create("demo-skill", "正文")
        escaped = json.loads(
            self.catalog.load("demo-skill", filename="../../secrets.txt")
        )
        self.assertIn("error", escaped)


if __name__ == "__main__":
    unittest.main()
