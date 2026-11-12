"""以 streamable HTTP 传输启动 MCP 服务器（默认 http://127.0.0.1:8000/mcp）。

    python run.py
    # 或
    python -m mcp_anythingllm      # 等价入口
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR / "src"))

from mcp_anythingllm.config import settings
from mcp_anythingllm.server import mcp

if __name__ == "__main__":
    import uvicorn

    if not settings.api_key:
        # 不阻止启动：MCP 客户端能连上并看到工具清单，调用时才报 CONFIG_ERROR
        print(
            "[warn] 未检测到 ANYTHINGLLM_API_KEY，工具调用会返回 CONFIG_ERROR。"
            f"请在 {BASE_DIR / '.env'} 中配置。",
            file=sys.stderr,
        )

    print(
        f"[info] AnythingLLM: {settings.base_url} | MCP: "
        f"http://{settings.host}:{settings.port}{settings.path}",
        file=sys.stderr,
    )
    # 注意 streamable_http_app 是方法而不是属性，必须调用才拿到 ASGI 应用
    app = mcp.streamable_http_app(streamable_http_path=settings.path)
    uvicorn.run(app, host=settings.host, port=settings.port, log_level="info")
