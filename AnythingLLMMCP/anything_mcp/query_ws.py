import os
from pathlib import Path

import httpx
from dotenv import load_dotenv

for parent in Path(__file__).resolve().parents:
    env_file = parent / ".env"
    if env_file.is_file():
        load_dotenv(env_file)
        break

headers = {"Authorization": f"Bearer {os.getenv('ANYTHINGLLM_API_KEY', '')}"}
try:
    r = httpx.get("http://localhost:3001/api/v1/workspaces", headers=headers)
    print(r.json())
except Exception as e:
    print(f"Error: {e}")
