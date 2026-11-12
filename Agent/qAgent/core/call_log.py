"""Structured tool-call log (JSONL, append-only).

One line per tool call:

    {"ts": "...", "event": "tool_call", "name": "read_text_file",
     "ok": false, "code": "PATH_OUTSIDE_WORKSPACE", "dur_ms": 3,
     "args": ["path"]}

Argument *values* are never logged — only the key names — because tool
arguments can carry file contents or credentials. The log lives under
``<workspace>/.agents/logs/tool-calls.jsonl`` so it travels with the session
and is ignored by git (``.agents/`` is in ``.gitignore``).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

LOG_DIRNAME = "logs"
LOG_FILENAME = "tool-calls.jsonl"

_logger = logging.getLogger("qagent.tools")


def log_path(workspace_root: Path | str) -> Path:
    return Path(workspace_root) / ".agents" / LOG_DIRNAME / LOG_FILENAME


class ToolCallLog:
    """Append-only JSONL journal of tool calls; failures never break a turn."""

    def __init__(self, workspace_root: Path | str, enabled: bool = True) -> None:
        self._path = log_path(workspace_root)
        self._enabled = enabled
        self._warned = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def path(self) -> Path:
        return self._path

    def record(self, name: str, *, ok: bool, dur_ms: int, result: str = "", arguments: Any = None) -> None:
        """Append one call record. Serialization errors are swallowed."""

        if not self._enabled:
            return
        entry: dict[str, Any] = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "event": "tool_call",
            "name": name,
            "ok": ok,
            "dur_ms": dur_ms,
        }
        code = error_code(result)
        if code:
            entry["code"] = code
        if isinstance(arguments, dict):
            # Key names only: values may contain file contents or secrets.
            entry["args"] = sorted(str(key) for key in arguments)
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError as exc:  # logging must never break the conversation
            if not self._warned:
                self._warned = True
                _logger.warning("工具调用日志写入失败（%s）：%s", self._path, exc)

    def tail(self, limit: int = 20) -> list[dict[str, Any]]:
        """Most recent records, newest last (used by ``/tools`` style views)."""

        if not self._path.is_file():
            return []
        lines: list[str] = []
        try:
            with self._path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    lines.append(line)
        except OSError:
            return []
        records: list[dict[str, Any]] = []
        for line in lines[-limit:]:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return records


def error_code(result: str) -> str:
    """Extract ``code`` from an ``{"error": ..., "code": ...}`` tool result."""

    if not result.startswith("{"):
        return ""
    try:
        payload = json.loads(result)
    except json.JSONDecodeError:
        return ""
    if not isinstance(payload, dict) or "error" not in payload:
        return ""
    return str(payload.get("code") or "TOOL_ERROR")
