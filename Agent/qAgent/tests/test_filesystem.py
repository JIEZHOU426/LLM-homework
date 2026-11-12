"""Filesystem tools: the ten semantic categories, argument errors and confinement."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from core.tools.filesystem import FileSystemTools
from core.tools.registry import ToolRegistry


def _payload(raw: str) -> dict:
    return json.loads(raw)


class FileSystemToolsTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()
        self.registry = ToolRegistry(
            FileSystemTools(2 * 1024 * 1024, workspace_root=self.root, confine=True).build()
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def call(self, name: str, **arguments: object) -> dict:
        return _payload(self.registry.execute(name, json.dumps(arguments)))

    def test_create_read_edit_append(self) -> None:
        created = self.call(
            "create_file",
            directory=str(self.root / "notes"),
            filename="todo.txt",
            content="第一行",
        )
        self.assertNotIn("error", created)
        path = self.root / "notes" / "todo.txt"
        self.assertTrue(path.is_file())

        read = self.call("read_text_file", path=str(path))
        self.assertEqual(read["content"], "第一行")

        appended = self.call("edit_file", path=str(path), content="\n第二行", mode="append")
        self.assertEqual(appended["mode"], "append")
        self.assertEqual(path.read_text(encoding="utf-8"), "第一行\n第二行")

        overwritten = self.call("edit_file", path=str(path), content="重置")
        self.assertEqual(overwritten["mode"], "overwrite")
        self.assertEqual(path.read_text(encoding="utf-8"), "重置")

    def test_create_file_refuses_to_overwrite(self) -> None:
        self.call("create_file", directory=str(self.root), filename="a.txt", content="x")
        again = self.call(
            "create_file", directory=str(self.root), filename="a.txt", content="y"
        )
        self.assertIn("error", again)
        self.assertEqual((self.root / "a.txt").read_text(encoding="utf-8"), "x")

    def test_create_file_rejects_path_in_filename(self) -> None:
        result = self.call(
            "create_file", directory=str(self.root), filename="../escape.txt"
        )
        self.assertIn("error", result)

    def test_list_and_type(self) -> None:
        (self.root / "sub").mkdir()
        (self.root / "sub" / "data.bin").write_bytes(b"\x00\x01")
        (self.root / "hello.txt").write_text("hi", encoding="utf-8")

        listing = self.call("list_directory", path=str(self.root))
        names = {entry["name"] for entry in listing["entries"]}
        self.assertEqual(names, {"sub", "hello.txt"})
        kinds = {entry["name"]: entry["type"] for entry in listing["entries"]}
        self.assertEqual(kinds["sub"], "directory")
        self.assertEqual(kinds["hello.txt"], "file")

        info = self.call("get_file_type", path=str(self.root / "hello.txt"))
        self.assertEqual(info["kind"], "file")
        self.assertTrue(info["isText"])
        self.assertEqual(info["extension"], ".txt")

        binary = self.call("get_file_type", path=str(self.root / "sub" / "data.bin"))
        self.assertFalse(binary["isText"])

    def test_read_text_file_rejects_binary(self) -> None:
        target = self.root / "blob.bin"
        target.write_bytes(b"\x00\x01\x02")
        self.assertIn("error", self.call("read_text_file", path=str(target)))

    def test_create_directory_is_idempotent_error(self) -> None:
        first = self.call("create_directory", path=str(self.root / "a" / "b"))
        self.assertTrue(first["created"])
        second = self.call("create_directory", path=str(self.root / "a" / "b"))
        self.assertIn("error", second)

    def test_delete_rename_and_guard(self) -> None:
        target = self.root / "tmp.txt"
        target.write_text("x", encoding="utf-8")
        renamed = self.call(
            "rename_path", source=str(target), target=str(self.root / "tmp2.txt")
        )
        self.assertTrue(renamed["renamed"])
        self.assertEqual(self.call("delete_file", path=str(self.root / "tmp2.txt"))["deleted"], True)

        folder = self.root / "doomed"
        (folder / "inner").mkdir(parents=True)
        self.assertTrue(self.call("delete_directory", path=str(folder))["deleted"])
        self.assertFalse(folder.exists())

    def test_delete_file_on_directory_is_rejected(self) -> None:
        (self.root / "d").mkdir()
        result = self.call("delete_file", path=str(self.root / "d"))
        self.assertIn("delete_directory", result["error"])

    def test_boundary_blocks_outside_paths(self) -> None:
        outside = Path(tempfile.gettempdir()).resolve() / "qagent-outside-probe.txt"
        result = self.call("read_text_file", path=str(outside))
        self.assertIn("PATH_OUTSIDE_WORKSPACE", result["error"])
        # 相对路径逃离同样被拦
        escape = self.call("list_directory", path="../")
        self.assertIn("PATH_OUTSIDE_WORKSPACE", escape["error"])

    def test_boundary_can_be_disabled(self) -> None:
        open_registry = ToolRegistry(
            FileSystemTools(2 * 1024 * 1024, workspace_root=self.root, confine=False).build()
        )
        raw = open_registry.execute(
            "get_file_type", json.dumps({"path": str(Path(tempfile.gettempdir()))})
        )
        self.assertNotIn("PATH_OUTSIDE_WORKSPACE", raw)

    def test_missing_and_unknown_tool_errors(self) -> None:
        missing = _payload(self.registry.execute("read_text_file", "{}"))
        self.assertIn("缺少参数", missing["error"])
        unknown = _payload(self.registry.execute("nope", "{}"))
        self.assertIn("未知工具", unknown["error"])
        bad_json = _payload(self.registry.execute("get_cwd", "{not json"))
        self.assertIn("参数解析失败", bad_json["error"])


if __name__ == "__main__":
    unittest.main()
