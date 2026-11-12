"""Shared helpers for local tools."""

from __future__ import annotations

import json
import locale
from pathlib import Path
from typing import Any


def json_error(message: str, code: str | None = None) -> str:
    payload: dict[str, Any] = {"error": message}
    if code:
        payload["code"] = code
    return json.dumps(payload, ensure_ascii=False)


def json_ok(**payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False)


def resolve_path(raw: str) -> Path:
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("路径不能为空")
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve()


def ensure_within(path: Path, root: Path) -> Path:
    """Reject paths that escape ``root`` (``PATH_OUTSIDE_WORKSPACE``)."""

    resolved = path.resolve()
    boundary = root.resolve()
    if resolved == boundary or resolved.is_relative_to(boundary):
        return resolved
    raise ValueError(
        f"PATH_OUTSIDE_WORKSPACE: {resolved} 不在允许的工作目录 {boundary} 内"
        "（[files] confine_to_workspace = true；如需跨目录操作请改为 false）"
    )


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
