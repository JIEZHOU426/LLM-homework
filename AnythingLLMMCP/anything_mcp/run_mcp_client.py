"""端到端冒烟脚本：起一个本地 MCP HTTP 服务，再用 MCP 客户端真的调工具。

**需要**：AnythingLLM 已启动 + `ANYTHINGLLM_API_KEY` 已配置。它验证的是协议
链路与工具注册，不是 AnythingLLM 业务正确性；不需要后端的部分见
``tests/test_client.py``。

    python run_mcp_client.py
"""

import asyncio
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PORT = 8001


def wait_for_port(port: int, timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.2)
    return False


proc = subprocess.Popen(
    [
        sys.executable,
        "-c",
        "import sys; sys.path.insert(0, 'src'); "
        "from mcp_anythingllm.config import settings; "
        "from mcp_anythingllm.server import mcp; import uvicorn; "
        f"uvicorn.run(mcp.streamable_http_app(streamable_http_path=settings.path), "
        f"host='127.0.0.1', port={PORT}, log_level='warning')",
    ],
    cwd=str(BASE_DIR),
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
)


async def main() -> None:
    from mcp import ClientSession

    # SDK 2.3 叫 streamable_http_client，1.x/早期 2.x 叫 streamablehttp_client，
    # 两个都试一遍，避免锁版本不同就 import 失败
    try:
        from mcp.client.streamable_http import streamable_http_client as http_client
    except ImportError:  # pragma: no cover - 兼容旧 SDK
        from mcp.client.streamable_http import streamablehttp_client as http_client

    url = f"http://127.0.0.1:{PORT}/mcp"
    # 传输层返回 (read, write[, get_session_id])，session 要自己建
    async with http_client(url) as streams:
        read_stream, write_stream = streams[0], streams[1]
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            tools = await session.list_tools()
            print("== 已注册工具 ==")
            for tool in tools.tools:
                print(f"- {tool.name}: {(tool.description or '').splitlines()[0]}")

            print("\n== list_workspaces ==")
            result = await session.call_tool("list_workspaces", {})
            print(result.content[0].text if result.content else result)

            slug = os.getenv("ANYTHINGLLM_WORKSPACE", "default")
            print(f"\n== workspace_chat(slug={slug}) ==")
            result = await session.call_tool(
                "workspace_chat",
                {"workspace_slug": slug, "question": "这个工作区里收录了哪些主题？"},
            )
            for item in result.content:
                print(item.text)
            print("is_error:", result.is_error)


try:
    if not wait_for_port(PORT):
        raise SystemExit(f"服务未在 127.0.0.1:{PORT} 上就绪，请查看上面的日志")
    asyncio.run(main())
finally:
    proc.terminate()
    try:
        out, err = proc.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, err = proc.communicate()
    if err and err.strip():
        print("--- server stderr ---", file=sys.stderr)
        print(err.decode("utf-8", "ignore")[-2000:], file=sys.stderr)
