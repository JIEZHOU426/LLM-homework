import json

import httpx

payload = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
        "name": "workspace_chat",
        "arguments": {"workspace_slug": "default", "question": "陈建是谁？"},
    },
}
r = httpx.post(
    "http://127.0.0.1:8001/mcp",
    json=payload,
    headers={"Content-Type": "application/json"},
    timeout=30,
)
print(r.text)
