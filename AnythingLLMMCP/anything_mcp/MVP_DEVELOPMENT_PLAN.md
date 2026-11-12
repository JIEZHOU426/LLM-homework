# AnythingLLM MCP Server — 设计与实施计划

> 状态：**已实现**（`src/mcp_anythingllm`）。本文记录设计取舍、实施步骤与
> 验证方式，与代码保持一致；如有出入以代码与单元测试为准。

## 1. 目标

把本地 AnythingLLM 的知识库能力暴露成 MCP 工具，让任意 MCP 客户端（IDE 插件、
命令行 Agent）可以在不改协议、不搬文档的前提下：

1. 知道有哪些工作区（及其 slug）；
2. 就某个工作区的文档提问并拿到带检索的回答；
3. 把一段新资料灌进工作区**并完成向量化**；
4. 直接看某句 query 命中了哪些片段（核查召回，而不是只看生成结果）。

非目标：替代 AnythingLLM 的管理后台（不改系统设置、不做用户管理）、不做多轮
会话状态管理（每次调用独立）。

## 2. 技术栈与传输

| 项 | 选择 | 理由 |
| --- | --- | --- |
| 协议 | MCP（`mcp>=2.0`，`MCPServer` 这一代 API） | 与宠物医院 MCP 保持同一代 API，便于对照 |
| 传输 | streamable HTTP（`uvicorn` 承载 `streamable_http_app()`） | 长驻服务、可多客户端连接；stdio 模式与"启动一个 HTTP 服务"混在一起是之前配置错误的根源 |
| HTTP 客户端 | `httpx.AsyncClient` | 原生 async，超时/异常语义清晰 |
| 配置 | `.env` + 环境变量（`python-dotenv`） | 密钥不进仓库，客户端不必重复填 |

## 3. 工具设计

| 工具 | 端点 | 关键取舍 |
| --- | --- | --- |
| `list_workspaces` | `GET /api/v1/workspaces` | 只回 `id/name/slug/chatMode`，避免整份 workspace 元数据（含全部文档）撑爆上下文 |
| `workspace_chat` | `POST /api/v1/openai/chat/completions` | 复用 OpenAI 兼容端点，`model` 字段填 slug；返回纯文本回答 |
| `upload_and_embed_document` | `POST /api/v1/document/upload` + `POST /api/v1/workspace/{slug}/update-embeddings` | **两步合一**：只上传不 embed 的文件检索不到，模型极易漏第二步 |
| `vector_search` | `POST /api/v1/workspace/{slug}/vector-search` | 只回片段与 `score`，用于"哪份文档里有这句话"这类证据型问题 |

参数约束：`top_n` 1–20、`score_threshold` 0–1、`filename` 不得含路径、
`workspace_slug` 走白名单正则（因为它会被拼进 URL）。

## 4. 错误处理

统一 `ToolError(JSON)`：`code` / `message` / 可选 `status`、`detail`。

- `CONFIG_ERROR`：缺 API Key，**在发请求前**判定，避免把 401 当成业务错误；
- `VALIDATION_ERROR`：参数非法（slug、filename、范围）；
- `AUTH_FAILED`：401/403，独立错误码，提示"Key 无效"而不是"接口挂了"；
- `UPSTREAM_UNREACHABLE` / `UPSTREAM_TIMEOUT` / `UPSTREAM_HTTP_ERROR` /
  `UPSTREAM_BAD_PAYLOAD`：网络与响应层面的四类故障。

`detail` 只取上游的 `error`/`message` 字段或截断文本（160 字），不整段透传响应体
——整段 HTML 塞进模型上下文既浪费 token，也容易让模型误判。

## 5. 实施步骤（已完成）

1. `config.py`：加载就近 `.env`，暴露 base_url / api_key / host / port / timeout；
2. `anythingllm.py`：`_request` 统一做鉴权头、超时、错误码映射；4 个业务方法；
3. `server.py`：4 个 `@mcp.tool()`，每个都写清楚"什么时候该用它"；
4. `run.py` / `__main__.py`：`streamable_http_app(streamable_http_path=settings.path)`
   才是 ASGI 应用（它是方法不是属性），配 `uvicorn` 启动；缺 Key 只告警不阻断；
5. `run_mcp_client.py`：传输层客户端在 SDK 2.3 里叫 `streamable_http_client`
   （旧名 `streamablehttp_client`），返回 `(read, write)` 两条流；**自己建
   `ClientSession` 并 `initialize()`** 之后才能 `list_tools` / `call_tool`
   （之前的写法把 transport 的返回值当 session 用，且 import 的是新版已改名的
   函数，调不通）；
6. `tests/test_client.py`：13 个 `unittest`，`httpx.MockTransport` 拦网络；
7. 清理调试脚本，`.mcp.json` / `opencode.json` 改成 remote `url` 形式。

## 6. 验证

```bash
cd anything_mcp
python -m unittest discover -s tests -t . -v     # 13 passed
uv run python run.py                             # 服务起在 127.0.0.1:8000/mcp
uv run python run_mcp_client.py                  # 需要 AnythingLLM 在运行
```

验收标准：

- [x] 四个工具都能在 `list_tools` 中看到并带说明；
- [x] 缺 Key 返回 `CONFIG_ERROR` 且不发出请求；
- [x] 上传后确实调用了 `update-embeddings` 且 `adds` 是上传返回的 `location`；
- [x] 401 与 500 返回不同错误码；
- [x] 客户端注册形式为 `url`（streamable HTTP），不是 `command`。

## 7. 后续可做

- 支持 `POST /api/v1/workspace/{slug}/chat`（原生端点，可返回 `sources` 引用列表）；
- 批量上传目录（多文件一次 embed）；
- `stateless` 模式与鉴权（MCP 侧目前只监听 127.0.0.1）。
