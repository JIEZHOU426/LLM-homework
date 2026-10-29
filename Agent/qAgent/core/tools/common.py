"""Shared helpers for local tools."""

from __future__ import annotations

import json
import locale
from pathlib import Path
from typing import Any


def json_error(message: str) -> str:
    return json.dumps({"error": message}, ensure_ascii=False)


def json_ok(**payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False)


def resolve_path(raw: str) -> Path:
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("路径不能为空")
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve()


def detect_encoding(data: bytes) -> str | None:
    for encoding in ("utf-8", locale.getpreferredencoding(False), "gbk"):
        try:
            data.decode(encoding)
            return encoding
        except (UnicodeDecodeError, LookupError):
            continue
    return None


def is_text_data(data: bytes) -> bool:
    if b"\x00" in data:
        return False
    return detect_encoding(data) is not None


def read_file_content(path: Path, max_text_bytes: int) -> tuple[str, str]:
    size = path.stat().st_size
    if size > max_text_bytes:
        raise ValueError(
            f"文件过大（{size} 字节），超过读取上限 {max_text_bytes} 字节"
        )
    data = path.read_bytes()
    if b"\x00" in data:
        raise ValueError("仅支持纯文本文件：检测到二进制内容")
    encoding = detect_encoding(data)
    if encoding is None:
        raise ValueError("仅支持纯文本文件：无法识别文本编码")
    return data.decode(encoding), encoding


def ensure_safe_delete(path: Path) -> None:
    resolved = path.resolve()
    cwd = Path.cwd().resolve()
    forbidden = {Path(resolved.anchor).resolve(), Path.home().resolve(), cwd}
    if resolved in forbidden or resolved in cwd.parents:
        raise ValueError(f"出于安全考虑，不允许删除该目录: {resolved}")
