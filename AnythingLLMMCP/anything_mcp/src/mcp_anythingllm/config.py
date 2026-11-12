"""配置：全部来自环境变量 / 就近的 .env 文件。

`.`env` 的查找顺序与运行方式无关：从本文件所在目录逐级向上找到第一个 `.env`
（通常是 `anything_mcp/.env`，也兼容放在 `AnythingLLMMCP/.env` 的老布局）。
"""

from dataclasses import dataclass
from os import getenv
from pathlib import Path

from dotenv import load_dotenv

for parent in Path(__file__).resolve().parents:
    env_file = parent / ".env"
    if env_file.is_file():
        load_dotenv(env_file)
        break


@dataclass(frozen=True)
class Settings:
    base_url: str = getenv("ANYTHINGLLM_BASE_URL", "http://localhost:3001")
    api_key: str = getenv("ANYTHINGLLM_API_KEY", "")
    host: str = getenv("MCP_HOST", "127.0.0.1")
    port: int = int(getenv("MCP_PORT", "8000"))
    timeout: float = float(getenv("ANYTHINGLLM_TIMEOUT", "30"))
    # 暴露给 MCP 客户端的 HTTP 路径（streamable HTTP 传输的固定入口）
    path: str = "/mcp"


settings = Settings()
