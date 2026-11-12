"""Application configuration.

Configuration is resolved once at startup and passed explicitly to the rest
of the core. No module other than this one reads environment variables or
files. Every tunable parameter has a module-level default here; ``config.ini``
values simply override them.
"""

from __future__ import annotations

import configparser
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
DEFAULT_MODEL = "deepseek-chat"
DEFAULT_MAX_TEXT_BYTES = 2 * 1024 * 1024
# 无法从配置获得上下文窗口大小时使用该默认值（UI 会标注「默认」）
DEFAULT_CONTEXT_WINDOW = 131072
DEFAULT_COMPACT_THRESHOLD = 0.6
DEFAULT_SUMMARY_TOKENS = 5000
DEFAULT_REQUEST_TIMEOUT = 120.0
DEFAULT_MCP_REQUEST_TIMEOUT = 120.0
DEFAULT_MCP_CONNECT_TIMEOUT = 20.0
DEFAULT_TOOL_RESULT_MAX_CHARS = 4000
DEFAULT_MAX_STEPS = 12
DEFAULT_TURN_TIMEOUT = 600.0
DEFAULT_AGENTS_FILE = "AGENT.md"

# 占位 Key（模板生成的 mock 信息），检测到时视为未配置
_PLACEHOLDER_KEY_PREFIX = "sk-your"


class ConfigurationError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True, slots=True)
class Settings:
    """Immutable runtime settings shared by every front-end."""

    api_key: str
    configured: bool = True
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    max_text_bytes: int = DEFAULT_MAX_TEXT_BYTES
    request_timeout: float = DEFAULT_REQUEST_TIMEOUT
    mcp_request_timeout: float = DEFAULT_MCP_REQUEST_TIMEOUT
    mcp_connect_timeout: float = DEFAULT_MCP_CONNECT_TIMEOUT
    tool_result_max_chars: int = DEFAULT_TOOL_RESULT_MAX_CHARS
    baidu_search_api_key: str = ""
    context_window: int = 0  # 0 = 未知，使用 DEFAULT_CONTEXT_WINDOW
    compact_threshold: float = DEFAULT_COMPACT_THRESHOLD
    compact_summary_tokens: int = DEFAULT_SUMMARY_TOKENS
    max_steps: int = DEFAULT_MAX_STEPS
    turn_timeout: float = DEFAULT_TURN_TIMEOUT
    confine_paths: bool = True
    agents_filename: str = DEFAULT_AGENTS_FILE
    tool_log_enabled: bool = True
    project_root: Path = Path(".")
    workspace_root: Path = Path(".")
    config_files: tuple[Path, ...] = ()

    @classmethod
    def load(cls, project_root: Path | None = None) -> "Settings":
        """Load settings from ``.env`` and ``config.ini``.

        Files are searched in the current workspace (``Path.cwd()``) first and
        fall back to the qAgent installation directory; workspace values win
        because they are parsed last. Unlike earlier versions this method
        never raises when the key is a placeholder: instead ``configured``
        becomes ``False`` and front-ends can react in their own way (boot-
        strap dialog, disabled input, ...).
        """

        root = Path(project_root or Path(__file__).resolve().parent.parent).resolve()
        workspace_root = Path.cwd().resolve()

        load_dotenv(root / ".env")
        load_dotenv(workspace_root / ".env", override=True)  # workspace wins

        config_files: list[Path] = []
        if (root / "config.ini").exists():
            config_files.append(root / "config.ini")
        if (workspace_root / "config.ini").exists():
            config_files.append(workspace_root / "config.ini")  # later wins
        parser = configparser.ConfigParser()
        if config_files:
            parser.read(config_files, encoding="utf-8")

        api_key = (
            os.getenv("DEEPSEEK_API_KEY")
            or parser.get("LLM", "api_key", fallback="")
        ).strip()
        configured = bool(api_key) and not api_key.startswith(
            _PLACEHOLDER_KEY_PREFIX
        )

        base_url = (
            os.getenv("DEEPSEEK_BASE_URL")
            or parser.get("LLM", "base_url", fallback=DEFAULT_BASE_URL)
        ).strip()
        model = (
            os.getenv("DEEPSEEK_MODEL")
            or parser.get("LLM", "model", fallback=DEFAULT_MODEL)
        ).strip()

        max_text_bytes = _read_int(
            parser,
            "files",
            "max_text_bytes",
            DEFAULT_MAX_TEXT_BYTES,
        )
        request_timeout = _read_float(
            parser,
            "LLM",
            "timeout",
            DEFAULT_REQUEST_TIMEOUT,
        )
        mcp_request_timeout = _read_float(
            parser,
            "mcp",
            "request_timeout",
            DEFAULT_MCP_REQUEST_TIMEOUT,
        )
        mcp_connect_timeout = _read_float(
            parser,
            "mcp",
            "connect_timeout",
            DEFAULT_MCP_CONNECT_TIMEOUT,
        )
        tool_result_max_chars = _read_int(
            parser,
            "ui",
            "tool_result_max_chars",
            DEFAULT_TOOL_RESULT_MAX_CHARS,
        )
        baidu_search_api_key = (
            os.getenv("BAIDU_SEARCH_API_KEY")
            or parser.get("search", "baidu_api_key", fallback="")
        ).strip()
        # 仅当显式配置了 context_window 时才认为窗口已知，否则视为未知。
        if parser.has_option("LLM", "context_window"):
            context_window = _read_int(
                parser, "LLM", "context_window", 0
            )
        else:
            context_window = 0
        compact_threshold = _read_float(
            parser,
            "compact",
            "threshold",
            DEFAULT_COMPACT_THRESHOLD,
        )
        if not 0.0 < compact_threshold <= 1.0:
            compact_threshold = DEFAULT_COMPACT_THRESHOLD
        compact_summary_tokens = _read_int(
            parser,
            "compact",
            "summary_tokens",
            DEFAULT_SUMMARY_TOKENS,
        )
        if compact_summary_tokens <= 0:
            compact_summary_tokens = DEFAULT_SUMMARY_TOKENS

        max_steps = _read_int(parser, "agent", "max_steps", DEFAULT_MAX_STEPS)
        if max_steps <= 0:
            max_steps = DEFAULT_MAX_STEPS
        turn_timeout = _read_float(
            parser, "agent", "turn_timeout", DEFAULT_TURN_TIMEOUT
        )
        if turn_timeout <= 0:
            turn_timeout = DEFAULT_TURN_TIMEOUT
        confine_paths = _read_bool(parser, "files", "confine_to_workspace", True)
        agents_filename = (
            os.getenv("QAGENT_AGENTS_FILE")
            or parser.get("agents", "filename", fallback=DEFAULT_AGENTS_FILE)
        ).strip() or DEFAULT_AGENTS_FILE
        tool_log_enabled = _read_bool(parser, "log", "enabled", True)

        return cls(
            api_key=api_key,
            configured=configured,
            base_url=base_url or DEFAULT_BASE_URL,
            model=model or DEFAULT_MODEL,
            max_text_bytes=max_text_bytes,
            request_timeout=request_timeout,
            mcp_request_timeout=mcp_request_timeout,
            mcp_connect_timeout=mcp_connect_timeout,
            tool_result_max_chars=tool_result_max_chars,
            baidu_search_api_key=baidu_search_api_key,
            compact_threshold=compact_threshold,
            compact_summary_tokens=compact_summary_tokens,
            context_window=context_window,
            max_steps=max_steps,
            turn_timeout=turn_timeout,
            confine_paths=confine_paths,
            agents_filename=agents_filename,
            tool_log_enabled=tool_log_enabled,
            project_root=root,
            workspace_root=workspace_root,
            config_files=tuple(config_files),
        )


def _read_int(
    parser: configparser.ConfigParser,
    section: str,
    option: str,
    default: int,
) -> int:
    try:
        return parser.getint(section, option, fallback=default)
    except ValueError:
        return default


def _read_float(
    parser: configparser.ConfigParser,
    section: str,
    option: str,
    default: float,
) -> float:
    try:
        return parser.getfloat(section, option, fallback=default)
    except ValueError:
        return default


def _read_bool(
    parser: configparser.ConfigParser,
    section: str,
    option: str,
    default: bool,
) -> bool:
    try:
        return parser.getboolean(section, option, fallback=default)
    except ValueError:
        return default
