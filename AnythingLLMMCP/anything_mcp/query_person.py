import json
import os
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

for parent in Path(__file__).resolve().parents:
    env_file = parent / ".env"
    if env_file.is_file():
        load_dotenv(env_file)
        break

url = (
    "http://localhost:3001/api/v1/workspace/"
    "46decf1f-7fe5-4d03-9584-9d2b6f2743a0/chat"
)
headers = {
    "Authorization": f"Bearer {os.getenv('ANYTHINGLLM_API_KEY', '')}",
    "Content-Type": "application/json",
}
payload = {
    "prompt": "陈建这个人怎么样？请根据工作区中的文档详细介绍。",
    "searchTopK": 5,
    "searchScoreThreshold": 0.2,
}
req = urllib.request.Request(
    url,
    data=json.dumps(payload).encode("utf-8"),
    headers=headers,
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        print(resp.read().decode("utf-8"))
except Exception as e:
    print(f"Error: {e}")
