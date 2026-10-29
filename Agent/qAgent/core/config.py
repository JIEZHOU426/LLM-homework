"""Application configuration.

Configuration is resolved once at startup and passed explicitly to the rest of
the core. No module other than this one reads environment variables or files.
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


class ConfigurationError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True, slots=True)
class Settings:
    """Immutable runtime settings shared by every front-end."""

    api_key: str
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    max_text_bytes: int = DEFAULT_MAX_TEXT_BYTES
    request_timeout: float = 120.0
    baidu_search_api_key: str = ""
    project_root: Path = Path(".")

    @classmethod
    def load(cls, project_root: Path | None = None) -> "Settings":
        """Load settings from ``.env`` and ``config.ini``.

        ``DEEPSEEK_API_KEY`` takes precedence over ``config.ini``. The API key
        is validated here so that front-ends can report the problem in their own
        way instead of crashing during import.
        """

        root = Path(project_root or Path(__file__).resolve().parent.parent).resolve()

        load_dotenv(root / ".env")
        load_dotenv()

        parser = configparser.ConfigParser()
        parser.read(root / "config.ini", encoding="utf-8")

        api_key = (
            os.getenv("DEEPSEEK_API_KEY")
            or parser.get("LLM", "api_key", fallback="")
        ).strip()
        if not api_key or api_key.startswith("sk-your"):
            raise ConfigurationError(
                "未配置 API Key：请在 .env 中设置 DEEPSEEK_API_KEY，"
                "或在 config.ini 的 [LLM] 中填写 api_key。"
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
            120.0,
        )
        baidu_search_api_key = (
            os.getenv("BAIDU_SEARCH_API_KEY")
            or parser.get("search", "baidu_api_key", fallback="")
        ).strip()

        return cls(
            api_key=api_key,
            base_url=base_url or DEFAULT_BASE_URL,
            model=model or DEFAULT_MODEL,
            max_text_bytes=max_text_bytes,
            request_timeout=request_timeout,
            baidu_search_api_key=baidu_search_api_key,
            project_root=root,
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
