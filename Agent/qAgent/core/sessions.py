"""Session persistence: JSONL event logs under ``<workspace>/.agents/sessions``.

A session file is an append-style event log with one JSON object per line:

- ``{"type": "meta", ...}`` header: session id, timestamps, title, counts.
- ``{"type": "agents_md", ...}``: the AGENTS.md context message injected once
  at the start of the session (see :mod:`core.agent`). Persisting it here
  means a resumed session re-uses exactly the same injected message, which
  keeps the prompt cache valid across restarts.
- ``{"type": "message", "message": {...}}``: one conversation message
  (user / assistant / tool) exactly as stored in ``ChatAgent`` history.

The format mirrors ``core.compact`` artifact layout so both feature sets stay
consistent and inspectable.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

SESSIONS_DIR_PARTS = (".agents", "sessions")
SESSION_SUFFIX = ".jsonl"
TITLE_MAX_CHARS = 48
_TITLE_PLACEHOLDER = "（未命名会话）"


def sessions_directory(workspace_root: Path | str) -> Path:
    """The ``<workspace>/.agents/sessions`` directory."""

    return Path(workspace_root) / Path(*SESSIONS_DIR_PARTS)


def session_stamp(now: datetime | None = None) -> str:
    """File-stamp used as session id, e.g. ``20261106-153000``."""

    return (now or datetime.now()).strftime("%Y%m%d-%H%M%S")


def _iso(stamp: str) -> str:
    """Human display form of a session stamp."""

    try:
        parsed = datetime.strptime(stamp, "%Y%m%d-%H%M%S")
        return parsed.strftime("%m-%d %H:%M")
    except ValueError:
        return stamp


def _extract_title(messages: list[dict[str, Any]]) -> str:
    for message in messages:
        if message.get("role") != "user":
            continue
        text = str(message.get("content") or "").strip()
        if not text:
            continue
        first = text.splitlines()[0].strip()
        if len(first) > TITLE_MAX_CHARS:
            first = first[: TITLE_MAX_CHARS - 1] + "…"
        return first or _TITLE_PLACEHOLDER
    return _TITLE_PLACEHOLDER


@dataclass(frozen=True, slots=True)
class SessionSummary:
    """One row of the ``/resume`` session list."""

    path: Path
    session_id: str
    created_at: str = ""
    updated_at: str = ""
    title: str = _TITLE_PLACEHOLDER
    model: str = ""
    message_count: int = 0

    @property
    def display_created(self) -> str:
        return _iso(self.created_at)

    @property
    def display_updated(self) -> str:
        return _iso(self.updated_at)


@dataclass(frozen=True, slots=True)
class SessionLog:
    """The fully parsed event log, ready for replay into a ``ChatAgent``."""

    summary: SessionSummary
    agents_md: dict[str, Any] | None = None
    messages: list[dict[str, Any]] = field(default_factory=list)


def save_session(
    workspace_root: Path | str,
    *,
    session_id: str,
    created_at: str,
    messages: list[dict[str, Any]],
    agents_md: dict[str, Any] | None = None,
    updated_at: str | None = None,
    model: str = "",
) -> Path:
    """Rewrite (atomically) the event log file for ``session_id``.

    Simple full rewrite keeps the writer deterministic; files are small enough
    that the cost is negligible compared to an LLM turn.
    """

    directory = sessions_directory(workspace_root)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{session_id}{SESSION_SUFFIX}"

    now = (datetime.now()).strftime("%Y%m%d-%H%M%S")
    header = {
        "type": "meta",
        "id": session_id,
        "created_at": created_at,
        "updated_at": updated_at or now,
        "model": model,
        "message_count": len(messages),
        "title": _extract_title(messages),
    }

    lines = [json.dumps(header, ensure_ascii=False)]
    if agents_md is not None:
        lines.append(
            json.dumps({"type": "agents_md", **agents_md}, ensure_ascii=False)
        )
    for index, message in enumerate(messages):
        record = {"type": "message", "index": index, "message": message}
        lines.append(json.dumps(record, ensure_ascii=False))

    tmp_path = path.with_suffix(".jsonl.tmp")
    tmp_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    tmp_path.replace(path)
    return path


def list_sessions(
    workspace_root: Path | str,
    limit: int = 100,
) -> list[SessionSummary]:
    """List available session logs, newest first."""

    directory = sessions_directory(workspace_root)
    if not directory.is_dir():
        return []

    files = sorted(
        (p for p in directory.glob(f"*{SESSION_SUFFIX}"))
        if directory.is_dir()
        else [],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )[:limit]

    summaries: list[SessionSummary] = []
    for path in files:
        summary = _read_summary(path)
        if summary is not None:
            summaries.append(summary)
    return summaries


def load_session(path: Path | str) -> SessionLog:
    """Parse one session event log for replay."""

    path = Path(path)
    meta: dict[str, Any] = {}
    agents_md: dict[str, Any] | None = None
    messages: list[dict[str, Any]] = []

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        kind = event.get("type")
        if kind == "meta":
            meta = event
        elif kind == "agents_md":
            agents_md = event
        elif kind == "message":
            message = event.get("message")
            if isinstance(message, dict):
                messages.append(message)

    summary = SessionSummary(
        path=path,
        session_id=str(meta.get("id", path.stem)),
        created_at=str(meta.get("created_at", "")),
        updated_at=str(meta.get("updated_at", "")),
        title=str(meta.get("title", "")) or _TITLE_PLACEHOLDER,
        model=str(meta.get("model", "")),
        message_count=len(messages),
    )
    return SessionLog(summary=summary, agents_md=agents_md, messages=messages)


def _read_summary(path: Path) -> SessionSummary | None:
    meta: dict[str, Any] = {}
    title = ""
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "meta":
            meta = event
            continue
        if event.get("type") == "message" and not title:
            message = event.get("message") or {}
            if message.get("role") == "user":
                first = str(message.get("content") or "").strip()
                if first:
                    first = first.splitlines()[0].strip()
                    if len(first) > TITLE_MAX_CHARS:
                        first = first[: TITLE_MAX_CHARS - 1] + "…"
                    title = first
            if meta and title:
                break
    if not meta:
        return None
    return SessionSummary(
        path=path,
        session_id=str(meta.get("id", path.stem)),
        created_at=str(meta.get("created_at", "")),
        updated_at=str(meta.get("updated_at", "")),
        title=str(meta.get("title", "")) or (title or _TITLE_PLACEHOLDER),
        model=str(meta.get("model", "")),
        message_count=int(meta.get("message_count", 0) or 0),
    )
