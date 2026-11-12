"""MCP 工具层：四个工具覆盖 AnythingLLM 的"看-问-灌-搜"四类动作。

| 工具 | 端点 | 解决什么问题 |
| --- | --- | --- |
| `list_workspaces` | `GET /api/v1/workspaces` | 模型先知道有哪些工作区、slug 是什么 |
| `workspace_chat` | `POST /api/v1/openai/chat/completions` | 基于工作区文档问答（RAG） |
| `upload_and_embed_document` | `POST /api/v1/document/upload` + `POST /api/v1/workspace/{slug}/update-embeddings` | 把一段文本灌进工作区**并完成向量化** |
| `vector_search` | `POST /api/v1/workspace/{slug}/vector-search` | 只检索片段与相似度，不生成回答（可核查召回） |

错误一律抛 `ToolError`（JSON 体：`code` / `message` / 可选 `status`、`detail`），
不要把异常字符串直接返回给模型——那样模型分不清"配置缺失"和"后端挂了"。
"""

from typing import Annotated

from mcp.server import MCPServer
from pydantic import Field

from mcp_anythingllm import AnythingLLMClient

mcp = MCPServer("anythingllm-mcp")


@mcp.tool()
async def list_workspaces() -> dict:
    """列出 AnythingLLM 中所有工作区。

    返回：`workspaces`（每项含 id、name、slug、chatMode）与 `total`。
    调用 `workspace_chat` / `vector_search` 前如果不知道 slug，先调本工具。
    """
    client = AnythingLLMClient()
    try:
        return await client.list_workspaces()
    finally:
        await client.close()


@mcp.tool()
async def workspace_chat(
    workspace_slug: Annotated[
        str,
        Field(description="工作区标识（slug），可在 list_workspaces 的返回里取"),
    ],
    question: Annotated[
        str,
        Field(description="要问的问题，使用工作区文档的语言提问效果最好"),
    ],
) -> str:
    """从指定 AnythingLLM 工作区的文档里检索并生成回答（RAG 问答）。

    AnythingLLM 自带向量检索与引用，本工具只负责把问题和 slug 转发过去，
    并把回答文本原样返回。
    """
    client = AnythingLLMClient()
    try:
        return await client.chat(workspace_slug, question)
    finally:
        await client.close()


@mcp.tool()
async def upload_and_embed_document(
    workspace_slug: Annotated[
        str, Field(description="目标工作区的 slug")
    ],
    filename: Annotated[
        str,
        Field(
            description="保存到工作区时的文件名（含扩展名，如 notes.md），不能带路径",
        ),
    ],
    content: Annotated[
        str,
        Field(description="文件全文（纯文本或 Markdown），会上传后立即向量化"),
    ],
) -> dict:
    """把一段文本上传到工作区，**并立刻完成向量化**，之后才能被问答检索到。

    分两步：先 `/document/upload` 拿到文档位置，再
    `/workspace/{slug}/update-embeddings` 提交向量化。只上传不 embed 的文件
    不会进入检索库，所以这里把两步合成了一个工具。

    返回：`documents`（含 location）、`embedded`（是否提交成功）、`message`。
    """
    client = AnythingLLMClient()
    try:
        return await client.upload_and_embed_document(
            workspace_slug, filename, content
        )
    finally:
        await client.close()


@mcp.tool()
async def vector_search(
    workspace_slug: Annotated[str, Field(description="工作区的 slug")],
    query: Annotated[str, Field(description="检索语句")],
    top_n: Annotated[
        int,
        Field(ge=1, le=20, description="返回的片段数量上限，默认 5"),
    ] = 5,
    score_threshold: Annotated[
        float | None,
        Field(ge=0, le=1, description="相似度阈值（0-1），低于该值的片段丢弃"),
    ] = None,
) -> dict:
    """在工作区里做语义检索，只返回命中的片段与相似度，不生成回答。

    用于"这句话在哪个文档里出现过"这类需要看召回证据的场景；要比对召回质量
    或确认文档是否真的入库时用它，而不是 workspace_chat。
    """
    client = AnythingLLMClient()
    try:
        return await client.vector_search(
            workspace_slug, query, top_n=top_n, score_threshold=score_threshold
        )
    finally:
        await client.close()
