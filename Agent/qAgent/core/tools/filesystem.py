"""Local filesystem tools.

These tools are deliberately grouped behind the same :class:`Tool` contract as
the clock tools. A future web or desktop front-end gets them for free.
"""

from __future__ import annotations

import mimetypes
import shutil
from pathlib import Path
from typing import Any, Mapping

from .base import FunctionTool, Tool, ToolSpec
from .common import (
    ensure_safe_delete,
    is_text_data,
    json_error,
    json_ok,
    read_file_content,
    resolve_path,
)


def _string_argument(
    arguments: Mapping[str, Any],
    key: str,
    *,
    default: str | None = None,
) -> str:
    if key not in arguments:
        if default is None:
            raise ValueError(f"缺少参数: {key}")
        return default
    value = arguments[key]
    if not isinstance(value, str):
        raise ValueError(f"参数 {key} 必须是字符串")
    return value


class FileSystemTools:
    def __init__(self, max_text_bytes: int) -> None:
        self._max_text_bytes = max_text_bytes

    def build(self) -> list[Tool]:
        return [
            FunctionTool(
                ToolSpec(
                    name="get_cwd",
                    description="获取当前工作目录的绝对路径",
                    parameters={
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                ),
                self._get_cwd,
            ),
            FunctionTool(
                ToolSpec(
                    name="list_directory",
                    description="列出指定目录下所有文件和子目录",
                    parameters={
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "目录路径，默认为当前工作目录",
                            }
                        },
                        "required": [],
                    },
                ),
                self._list_directory,
            ),
            FunctionTool(
                ToolSpec(
                    name="get_file_type",
                    description="获取指定文件的文件类型（MIME 类型、扩展名、文本/二进制）",
                    parameters={
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "文件路径",
                            }
                        },
                        "required": ["path"],
                    },
                ),
                self._get_file_type,
            ),
            FunctionTool(
                ToolSpec(
                    name="read_text_file",
                    description="读取指定纯文本文件的内容，非纯文本文件会返回错误",
                    parameters={
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "文件路径",
                            }
                        },
                        "required": ["path"],
                    },
                ),
                self._read_text_file,
            ),
            FunctionTool(
                ToolSpec(
                    name="create_file",
                    description="根据指定的目录和文件名创建新文件，目录不存在时会自动创建",
                    parameters={
                        "type": "object",
                        "properties": {
                            "directory": {
                                "type": "string",
                                "description": "文件所在目录",
                            },
                            "filename": {
                                "type": "string",
                                "description": "文件名，例如 notes.txt",
                            },
                            "content": {
                                "type": "string",
                                "description": "初始文本内容，默认为空",
                            },
                        },
                        "required": ["directory", "filename"],
                    },
                ),
                self._create_file,
            ),
            FunctionTool(
                ToolSpec(
                    name="edit_file",
                    description="编辑指定纯文本文件的内容，支持覆盖或追加",
                    parameters={
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "文件路径",
                            },
                            "content": {
                                "type": "string",
                                "description": "要写入的文本内容",
                            },
                            "mode": {
                                "type": "string",
                                "enum": ["overwrite", "append"],
                                "description": "编辑方式：overwrite 覆盖，append 追加，默认 overwrite",
                            },
                        },
                        "required": ["path", "content"],
                    },
                ),
                self._edit_file,
            ),
            FunctionTool(
                ToolSpec(
                    name="create_directory",
                    description="创建新目录，父目录不存在时会自动创建",
                    parameters={
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "要创建的目录路径",
                            }
                        },
                        "required": ["path"],
                    },
                ),
                self._create_directory,
            ),
            FunctionTool(
                ToolSpec(
                    name="delete_directory",
                    description="删除指定目录，非空目录会连同其中所有内容一起删除",
                    parameters={
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "要删除的目录路径",
                            }
                        },
                        "required": ["path"],
                    },
                ),
                self._delete_directory,
            ),
            FunctionTool(
                ToolSpec(
                    name="delete_file",
                    description="删除指定文件",
                    parameters={
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "要删除的文件路径",
                            }
                        },
                        "required": ["path"],
                    },
                ),
                self._delete_file,
            ),
            FunctionTool(
                ToolSpec(
                    name="rename_path",
                    description="重命名文件或目录，也可移动到新位置",
                    parameters={
                        "type": "object",
                        "properties": {
                            "source": {
                                "type": "string",
                                "description": "原文件或目录路径",
                            },
                            "target": {
                                "type": "string",
                                "description": "新的文件或目录路径",
                            },
                        },
                        "required": ["source", "target"],
                    },
                ),
                self._rename_path,
            ),
        ]

    def _get_cwd(self, _: Mapping[str, Any]) -> str:
        return json_ok(cwd=str(Path.cwd()))

    def _list_directory(self, arguments: Mapping[str, Any]) -> str:
        path = resolve_path(_string_argument(arguments, "path", default="."))
        if not path.exists():
            return json_error(f"目录不存在: {path}")
        if not path.is_dir():
            return json_error(f"不是目录: {path}")

        entries = []
        for child in sorted(
            path.iterdir(),
            key=lambda item: (not item.is_dir(), item.name.lower()),
        ):
            if child.is_symlink():
                kind = "symlink"
            elif child.is_dir():
                kind = "directory"
            elif child.is_file():
                kind = "file"
            else:
                kind = "other"
            entry: dict[str, Any] = {
                "name": child.name,
                "path": str(child),
                "type": kind,
            }
            if kind == "file":
                try:
                    entry["size"] = child.stat().st_size
                except OSError:
                    entry["size"] = None
            entries.append(entry)

        return json_ok(path=str(path), count=len(entries), entries=entries)

    def _get_file_type(self, arguments: Mapping[str, Any]) -> str:
        path = resolve_path(_string_argument(arguments, "path"))
        if not path.exists():
            return json_error(f"路径不存在: {path}")

        if path.is_symlink():
            kind = "symlink"
        elif path.is_dir():
            kind = "directory"
        elif path.is_file():
            kind = "file"
        else:
            kind = "other"

        result: dict[str, Any] = {
            "path": str(path),
            "kind": kind,
            "extension": path.suffix,
        }
        if kind != "file":
            return json_ok(**result)

        mime_type, mime_encoding = mimetypes.guess_type(path.name)
        with path.open("rb") as file:
            head = file.read(8192)
        result.update(
            {
                "mimeType": mime_type or "application/octet-stream",
                "mimeEncoding": mime_encoding,
                "isText": is_text_data(head),
                "size": path.stat().st_size,
            }
        )
        return json_ok(**result)

    def _read_text_file(self, arguments: Mapping[str, Any]) -> str:
        path = resolve_path(_string_argument(arguments, "path"))
        if not path.exists():
            return json_error(f"文件不存在: {path}")
        if not path.is_file():
            return json_error(f"不是文件: {path}")
        try:
            content, encoding = read_file_content(path, self._max_text_bytes)
        except (OSError, ValueError) as exc:
            return json_error(str(exc))
        return json_ok(
            path=str(path),
            encoding=encoding,
            size=path.stat().st_size,
            content=content,
        )

    def _create_file(self, arguments: Mapping[str, Any]) -> str:
        directory = _string_argument(arguments, "directory")
        filename = _string_argument(arguments, "filename")
        content = _string_argument(arguments, "content", default="")
        if not filename or Path(filename).name != filename:
            return json_error("filename 必须是文件名，不能包含路径分隔符")

        directory_path = resolve_path(directory)
        if directory_path.exists() and not directory_path.is_dir():
            return json_error(f"不是目录: {directory_path}")
        directory_path.mkdir(parents=True, exist_ok=True)

        file_path = (directory_path / filename).resolve()
        if file_path.exists():
            return json_error(f"文件已存在: {file_path}")

        file_path.write_text(content, encoding="utf-8")
        return json_ok(
            path=str(file_path),
            directory=str(directory_path),
            size=file_path.stat().st_size,
        )

    def _edit_file(self, arguments: Mapping[str, Any]) -> str:
        path = resolve_path(_string_argument(arguments, "path"))
        content = _string_argument(arguments, "content")
        mode = _string_argument(arguments, "mode", default="overwrite")
        if not path.exists():
            return json_error(f"文件不存在: {path}")
        if not path.is_file():
            return json_error(f"不是文件: {path}")
        if mode not in ("overwrite", "append"):
            return json_error("mode 只支持 overwrite 或 append")

        try:
            _, encoding = read_file_content(path, self._max_text_bytes)
        except (OSError, ValueError) as exc:
            return json_error(str(exc))

        if mode == "overwrite":
            path.write_text(content, encoding=encoding)
        else:
            with path.open("a", encoding=encoding, newline="") as file:
                file.write(content)

        return json_ok(
            path=str(path),
            mode=mode,
            encoding=encoding,
            size=path.stat().st_size,
        )

    def _create_directory(self, arguments: Mapping[str, Any]) -> str:
        path = resolve_path(_string_argument(arguments, "path"))
        if path.exists():
            if path.is_dir():
                return json_error(f"目录已存在: {path}")
            return json_error(f"路径已存在且不是目录: {path}")
        path.mkdir(parents=True, exist_ok=False)
        return json_ok(path=str(path), created=True)

    def _delete_directory(self, arguments: Mapping[str, Any]) -> str:
        path = resolve_path(_string_argument(arguments, "path"))
        if not path.exists():
            return json_error(f"目录不存在: {path}")
        if not path.is_dir() or path.is_symlink():
            return json_error(f"不是目录: {path}")
        try:
            ensure_safe_delete(path)
        except ValueError as exc:
            return json_error(str(exc))

        shutil.rmtree(path)
        return json_ok(path=str(path), deleted=True)

    def _delete_file(self, arguments: Mapping[str, Any]) -> str:
        path = resolve_path(_string_argument(arguments, "path"))
        if not path.exists() and not path.is_symlink():
            return json_error(f"文件不存在: {path}")
        if path.is_dir() and not path.is_symlink():
            return json_error(
                f"是目录而不是文件，请使用 delete_directory: {path}"
            )
        try:
            path.unlink()
        except OSError as exc:
            return json_error(str(exc))
        return json_ok(path=str(path), deleted=True)

    def _rename_path(self, arguments: Mapping[str, Any]) -> str:
        source_path = resolve_path(_string_argument(arguments, "source"))
        target_path = resolve_path(_string_argument(arguments, "target"))
        if not source_path.exists() and not source_path.is_symlink():
            return json_error(f"源路径不存在: {source_path}")
        if target_path.exists() or target_path.is_symlink():
            return json_error(f"目标路径已存在: {target_path}")
        try:
            shutil.move(str(source_path), str(target_path))
        except OSError as exc:
            return json_error(str(exc))
        return json_ok(
            source=str(source_path),
            target=str(target_path),
            renamed=True,
        )
