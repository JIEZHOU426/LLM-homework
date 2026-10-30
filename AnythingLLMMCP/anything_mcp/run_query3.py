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

import httpx

BASE = "http://127.0.0.1:8001/mcp"
headers = {"Content-Type": "application/json"}

try:
    r = httpx.post(
        BASE,
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "workspace_chat",
                "arguments": {"workspace_slug": "default", "question": "陈建是谁？"},
            },
        },
        headers=headers,
        timeout=30,
    )
    print("Raw response:", repr(r.text[:2000]))
    print("Status:", r.status_code)

    if r.text.startswith("event:"):
        for line in r.text.strip().split("\n"):
            if line.startswith("data: "):
                print(
                    "Parsed:",
                    json.dumps(json.loads(line[6:]), ensure_ascii=False, indent=2),
                )
finally:
    proc.terminate()
