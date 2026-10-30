import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR / "src"))

import uvicorn

from mcp_anythingllm.server import mcp

if __name__ == "__main__":
    uvicorn.run(mcp.streamable_http_app, host="127.0.0.1", port=8001)
