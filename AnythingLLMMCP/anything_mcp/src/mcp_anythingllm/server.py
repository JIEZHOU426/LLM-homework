import httpx
from mcp.server import MCPServer
from mcp_anythingllm import AnythingLLMClient

mcp = MCPServer("anythingllm-mcp")

@mcp.tool()
async def workspace_chat(
    workspace_slug: str,
    question: str,
) -> str:
    """从指定的 AnythingLLM 工作区中提取文档信息进行 AI 问答"""
    client = AnythingLLMClient()
    try:
        return await client.chat(workspace_slug, question)
    except httpx.HTTPStatusError as e:
        return f"AnythingLLM API 错误 ({e.response.status_code}): {e.response.text}"
    except Exception as e:
        return f"查询出错: {str(e)}"
    finally:
        await client.close()
