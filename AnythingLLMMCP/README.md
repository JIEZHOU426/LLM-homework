# AnythingLLM MCP 桥接服务

把本地 AnythingLLM 实例的检索问答能力封装成 MCP 工具，任何支持 MCP 的客户端
（opencode / VS Code / Claude Desktop / qAgent）都能直接"看工作区、问文档、
灌资料、查召回"。

## 目录结构

```text
AnythingLLMMCP/
├── README.md                 # 本文件
├── .env                      # 本地密钥（git 忽略）
└── anything_mcp/             # 唯一可发布代码
    ├── run.py                # 启动 streamable HTTP 服务（127.0.0.1:8000/mcp）
    ├── run_mcp_client.py     # 端到端冒烟：起服务 + MCP 客户端真实调用
    ├── .env.example          # 配置模板（复制为 .env）
    ├── opencode.json         # opencode 的 MCP 注册示例（remote 类型）
    ├── pyproject.toml
    ├── MVP_DEVELOPMENT_PLAN.md
    ├── src/mcp_anythingllm/
    │   ├── config.py         # 环境变量 / .env 加载
    │   ├── anythingllm.py    # REST 客户端：4 类调用 + 结构化错误
    │   ├── server.py         # 4 个 MCP 工具
    │   └── __main__.py       # python -m mcp_anythingllm
    └── tests/test_client.py  # 13 个单元测试（MockTransport，不联网）
```

## 快速开始

```bash
cd anything_mcp
uv sync                 # 或 pip install -e .
uv run python run.py    # 启动 MCP 服务：http://127.0.0.1:8000/mcp
```

在另一个终端跑端到端冒烟（需要 AnythingLLM 已在运行）：

```bash
uv run python run_mcp_client.py
```

## 配置

`config.py` 从本文件所在目录**逐级向上**寻找第一个 `.env`（`anything_mcp/.env`
或 `AnythingLLMMCP/.env` 都可以），因此密钥不必在每个 MCP 客户端里重复填。

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `ANYTHINGLLM_BASE_URL` | `http://localhost:3001` | AnythingLLM 服务地址 |
| `ANYTHINGLLM_API_KEY` | 空 | **必填**，AnythingLLM → Settings → API Keys 生成 |
| `ANYTHINGLLM_TIMEOUT` | `30` | 单次请求超时（秒） |
| `MCP_HOST` | `127.0.0.1` | MCP 服务监听地址（要跨机访问改成 `0.0.0.0`） |
| `MCP_PORT` | `8000` | MCP 服务端口 |

缺 `ANYTHINGLLM_API_KEY` 时服务仍能启动（客户端能看到工具清单），但每个工具
调用都会返回 `CONFIG_ERROR` 而不是让请求去撞一个 401。

## 接入 MCP 客户端

本服务是 **streamable HTTP** 传输，客户端配置要写 `url`，不是 `command`：

```json
{
  "mcp": {
    "anythingllm": { "type": "remote", "url": "http://127.0.0.1:8000/mcp", "enabled": true }
  }
}
```

VS Code / Claude 风格（`.mcp.json`）：

```json
{ "mcpServers": { "anythingllm": { "type": "http", "url": "http://127.0.0.1:8000/mcp" } } }
```

## 四个工具

| 工具 | 端点 | 用途 | 典型调用 |
| --- | --- | --- | --- |
| `list_workspaces` | `GET /api/v1/workspaces` | 先拿到 slug | 无参数 |
| `workspace_chat` | `POST /api/v1/openai/chat/completions` | 基于工作区文档问答（RAG） | `{workspace_slug:"course", question:"陈建是谁？"}` |
| `upload_and_embed_document` | `POST /api/v1/document/upload` → `POST /api/v1/workspace/{slug}/update-embeddings` | 灌资料**并向量化** | `{workspace_slug:"course", filename:"notes.md", content:"# ..."}` |
| `vector_search` | `POST /api/v1/workspace/{slug}/vector-search` | 只检索片段与相似度，用来核查召回 | `{workspace_slug:"course", query:"陈建", top_n:5}` |

设计要点：

- **上传与向量化合成一个工具**。AnythingLLM 里只上传不 embed 的文件不会进检索
  库，模型很容易只做第一步；工具把两步串起来，并回传 `embedded` 与 `documents[].location`。
- **问答与检索分开**。`workspace_chat` 给答案，`vector_search` 给证据（片段 +
  相似度），需要"为什么这么答"时用后者，不必再让模型猜。
- **`list_workspaces` 返回精简字段**（id/name/slug/chatMode），不把整份 workspace
  元数据（含文档列表）灌进模型上下文。

## 错误语义

失败一律抛 `ToolError`，消息体是 JSON，模型可据此决定重试还是改参数：

| code | 触发 | 建议动作 |
| --- | --- | --- |
| `CONFIG_ERROR` | 缺 `ANYTHINGLLM_API_KEY` | 提示用户配置，不要重试 |
| `VALIDATION_ERROR` | slug 非法、filename 带路径、空问题、topN/threshold 越界 | 改参数 |
| `AUTH_FAILED` | 401 / 403 | Key 无效或无权限，不要重试 |
| `UPSTREAM_UNREACHABLE` | 连不上 AnythingLLM | 提示服务未启动 |
| `UPSTREAM_TIMEOUT` | 请求超时 | 稍后重试 |
| `UPSTREAM_HTTP_ERROR` | 其余 4xx/5xx（带 `status`） | 按 `detail` 判断 |
| `UPSTREAM_BAD_PAYLOAD` | 返回非 JSON / 缺关键字段 | 报告后端异常 |

`workspace_slug` 会拼进 URL，因此先过白名单校验（字母数字点下划线连字符、
以字母数字开头），`../admin` 这类输入在发请求之前就被拒。

## 测试

```bash
cd anything_mcp
python -m unittest discover -s tests -t . -v
```

13 个用例，全部用 `httpx.MockTransport` 拦掉网络，覆盖：缺 Key、非法 slug、
工作区列表裁剪、问答请求体（`model` 字段承载 slug）、401 专用码、不可达/超时、
非 JSON 响应、上传→向量化两步的顺序与 `adds` 内容、上传缺 documents、检索参数
范围校验，以及"四个工具都已注册且有说明"。

## 设计文档

见 [`anything_mcp/MVP_DEVELOPMENT_PLAN.md`](anything_mcp/MVP_DEVELOPMENT_PLAN.md)。
