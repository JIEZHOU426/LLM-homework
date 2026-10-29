"""Date/time and leap-year tools."""

from __future__ import annotations

import locale
import subprocess
import sys
from typing import Any, Mapping

from .base import FunctionTool, Tool, ToolSpec
from .common import json_error, json_ok


def _get_date(_: Mapping[str, Any]) -> str:
    if sys.platform == "win32":
        command = "date /t & time /t"
    else:
        command = "date"
    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        encoding=locale.getpreferredencoding(False),
        errors="replace",
    )
    output = (result.stdout or "").strip()
    if result.returncode != 0:
        error = (result.stderr or "").strip()
        return json_error(error or "date command failed")
    return json_ok(datetime=output)


def _is_leap_year(year: int) -> bool:
    if year % 400 == 0:
        return True
    if year % 100 == 0:
        return False
    return year % 4 == 0


def _isleapyear(arguments: Mapping[str, Any]) -> str:
    try:
        year = int(arguments["year"])
    except (KeyError, TypeError, ValueError) as exc:
        return json_error(f"参数错误: {exc}")
    return json_ok(year=year, isLeapYear=_is_leap_year(year))


def build_clock_tools() -> list[Tool]:
    return [
        FunctionTool(
            ToolSpec(
                name="getDate",
                description="获取当前电脑的日期和时间，可用于回答今天是星期几、现在几点",
                parameters={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            ),
            _get_date,
        ),
        FunctionTool(
            ToolSpec(
                name="isleapyear",
                description="判断输入的年份是否为闰年",
                parameters={
                    "type": "object",
                    "properties": {
                        "year": {
                            "type": "integer",
                            "description": "要判断的年份，例如 2024",
                        }
                    },
                    "required": ["year"],
                },
            ),
            _isleapyear,
        ),
    ]
