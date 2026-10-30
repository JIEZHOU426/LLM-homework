# LLM-Course

LLM 相关课程代码与实验项目合集。

## 项目结构

| 目录 | 说明 |
|------|------|
| `anything_mcp/` | 基于 MCP 协议的 AnythingLLM 桥接服务器，提供工作区文档问答 Tool |
| `chongwu_mcp/` | 宠物医院 MCP 服务示例 |
| `Project1/` | 课程练习项目 1 |

## anything_mcp 快速开始

AnythingLLM MCP Server：作为 AnythingLLM 的桥接层，通过 MCP Tool `workspace_chat` 基于工作区文档进行 AI 问答。

### 环境要求

- Python 3.10+
- 本地运行的 AnythingLLM 实例（默认 `http://localhost:3001`）

### 安装

```bash
cd anything_mcp
uv sync
```

### 配置环境变量

在 `anything_mcp/`（或本目录）下创建 `.env` 文件（该文件已被 `.gitignore` 忽略，不会上传）：

```env
ANYTHINGLLM_BASE_URL=http://localhost:3001
ANYTHINGLLM_API_KEY=your-anythingllm-api-key
MCP_HOST=0.0.0.0
MCP_PORT=8000
```

`config.py` 会自动从当前项目目录向上查找并加载 `.env`，因此无需在 MCP 客户端里重复填写密钥。

### 启动服务

```bash
uv run python run.py
```

服务默认监听 `http://localhost:8000`，通过 Streamable HTTP 暴露 MCP 接口。

### 接入 MCP Client

在 MCP 客户端配置中注册该服务（示例，密钥由 `.env` 提供）：

```json
{
  "mcpServers": {
    "anythingllm": {
      "command": "py",
      "args": ["run.py"]
    }
  }
}
```

### 核心 Tool

- **`workspace_chat`**：输入 `workspace_slug` 与 `question`，基于 AnythingLLM 工作区中的文档知识返回 AI 回答。

### 文档

- 设计与实施计划见 [`anything_mcp/MVP_DEVELOPMENT_PLAN.md`](anything_mcp/MVP_DEVELOPMENT_PLAN.md)

> 提示：本目录下的 `src/`、`run.py` 等是根级工作副本，可通过 `.gitignore` 排除；可发布的代码位于 `anything_mcp/`。
