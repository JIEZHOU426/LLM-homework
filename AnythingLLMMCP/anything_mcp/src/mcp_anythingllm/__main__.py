"""``python -m mcp_anythingllm``：等价于 ``python run.py``。"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


def main() -> None:
    from mcp_anythingllm.config import settings
    from mcp_anythingllm.server import mcp

    import uvicorn

    app = mcp.streamable_http_app(streamable_http_path=settings.path)
    uvicorn.run(app, host=settings.host, port=settings.port, log_level="info")


if __name__ == "__main__":
    main()
