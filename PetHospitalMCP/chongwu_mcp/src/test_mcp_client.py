"""端到端冒烟脚本（**需要真实后端**，不属于单元测试）。

以 stdio 拉起 ``python -m pet_hospital_mcp``，列出工具并真实调用，用来验证
协议链路与后端联调。单元测试见 ``tests/test_tools.py``（不联网、不需要后端）。

    python src/test_mcp_client.py      # 先启动宠物医院后端（默认 8080）
"""

import asyncio
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC_DIR))

from mcp import ClientSession, StdioServerParameters, stdio_client


async def main():
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "pet_hospital_mcp"],
        cwd=str(SRC_DIR),
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print("== MCP 已注册工具 ==")
            for t in tools.tools:
                print(f"- {t.name}")

            print()
            print("== get_pets (species=犬, pageSize=1) ==")
            result = await session.call_tool("get_pets", {"species": "犬", "pageSize": 1})
            for c in result.content:
                print(c.text)

            print()
            print("== 边界: get_pets 无参数 ==")
            result = await session.call_tool("get_pets", {})
            for c in result.content:
                print("返回:", str(c))
            print("MCP is_error:", result.is_error)

            print()
            print("== 边界: add_pet 缺必填参数 ==")
            result = await session.call_tool("add_pet", {"name": "x"})
            for c in result.content:
                print("返回:", str(c)[:200])
            print("MCP is_error:", result.is_error)


if __name__ == "__main__":  # 避免被 unittest 等工具 import 时误执行
    asyncio.run(main())
