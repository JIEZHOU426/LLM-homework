"""Bootstrap of ``config.ini`` in the user's workspace.

If the current working directory has no ``config.ini``, a complete template
with mock (placeholder) values is created. The TUI then shows a dialog telling
the user to fill in real values and restart qAgent for them to take effect.
"""

from __future__ import annotations

import configparser
from pathlib import Path

CONFIG_FILENAME = "config.ini"

CONFIG_COMMENT = """\
; qAgent 配置文件 —— 已由程序自动生成（包含占位/mock 信息）。
; 修改下面所有占位内容并保存，然后重启 qAgent 才能正常工作。
"""

CONFIG_TEMPLATE = """\
[LLM]
; OpenAI 兼容 API Key（必填！请把下面的 mock 值替换成你的真实 Key）
api_key = sk-your-deepseek-key-here
base_url = https://api.deepseek.com/v1
; 模型名称（mock 默认值，可更换为任意 OpenAI 兼容模型）
model = deepseek-chat
; 请求超时（秒）
timeout = 120
; 模型上下文窗口大小（tokens）。不配置时按 131072（128k）默认值处理，
; 顶部栏会显示「（默认）」提示
; context_window = 65536

[files]
; 工具读写文本文件的大小上限（字节）
max_text_bytes = 2097152

[compact]
; 上下文用量达到该比例时告警并暂停新提示词，直到 /compact 完成
threshold = 0.6
; 压缩摘要的目标长度（tokens），同时作为摘要响应的 max_tokens 基准
summary_tokens = 5000

[mcp]
; MCP 工具调用超时与服务器连接超时（秒）
request_timeout = 120
connect_timeout = 20

[ui]
; 工具返回结果在 TUI 中展示的最大字符数
tool_result_max_chars = 4000

[search]
; 百度千帆联网搜索 API Key（可选；不填则 searchWeb 工具不可用）
baidu_api_key =
"""


def ensure_workspace_config(workspace_root: Path) -> bool:
    """Create a mock ``config.ini`` when missing. True if a file was created.

    An existing file whose API key is still the placeholder is *not*
    regenerated — the user may simply not have filled it in yet; the TUI
    reports the unconfigured state through ``Settings.configured`` instead.
    """

    path = workspace_root / CONFIG_FILENAME
    if path.exists():
        return False
    try:
        return _write_config(path)
    except OSError:
        return False


def _write_config(path: Path) -> bool:
    path.write_text(
        CONFIG_COMMENT + "\n" + CONFIG_TEMPLATE, encoding="utf-8"
    )
    parser = _parse(path)
    # sanity check the generated file is readable
    parser.get("LLM", "api_key")
    return True


def _parse(path: Path) -> configparser.ConfigParser:
    parser = configparser.ConfigParser()
    parser.read(path, encoding="utf-8")
    return parser
