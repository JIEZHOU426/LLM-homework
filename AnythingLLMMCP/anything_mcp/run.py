import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR / "src"))

from mcp_anythingllm.config import settings
from mcp_anythingllm.server import mcp

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(mcp.streamable_http_app, host=settings.host, port=settings.port)
