import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

proc = subprocess.Popen(
    [
        sys.executable,
        "-c",
        "import sys; sys.path.insert(0, 'src'); "
        "from mcp_anythingllm.server import mcp; import uvicorn; "
        "uvicorn.run(mcp.streamable_http_app, host='127.0.0.1', port=8001)",
    ],
    cwd=str(BASE_DIR),
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
)
print(f"Server PID: {proc.pid}")
time.sleep(2)

from mcp.client.streamable_http import streamablehttp_client


async def main():
    async with streamablehttp_client("http://127.0.0.1:8001/mcp") as client:
        result = await client.call_tool(
            "workspace_chat",
            {"workspace_slug": "default", "question": "陈建是谁？"},
        )
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


try:
    asyncio.run(main())
finally:
    proc.terminate()
