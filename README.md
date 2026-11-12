# LLM-homework

课程作业仓库：从一个命令行聊天程序出发，逐层走到**带 TUI 的本地 Agent**、
两个**自建 MCP 服务器**和一个**能真正把文档灌进知识库的网页**。

- 语言：Python 3.10+（qAgent 实际在 3.13 上验证）、Node.js 18+（网页代理）
- 依赖外部服务：DeepSeek（OpenAI 兼容 API）、百度千帆搜索（可选）、
  AnythingLLM（本地实例）、宠物医院后端 REST API（本地）
- 任何模块缺少密钥/服务时都会**给出明确错误提示**，不会静默失败

## 模块地图

| 目录 | 是什么 | 规模 | 怎么验证 |
| --- | --- | --- | --- |
| `Agent/Project1` | 极简单轮对话：流式输出、`---` 收尾 | 1 个脚本 | `py chat.py` |
| `Agent/Project2` | 多轮 + function call 的三个递进版本（`chat.py` → `chat_year.py` → `chat_file.py`） | 3 个脚本 + 架构图 | `py chat_file.py` |
| `Agent/qAgent` | **主交付物**：Textual TUI Agent，17 个本地工具、技能渐进加载、上下文压缩、会话持久化、MCP 客户端、工具调用护栏与日志 | 36 个 Python 文件 / 约 6.2k 行（含 tests） | `python -m unittest discover -s tests -t .`（36 个用例） |
| `PetHospitalMCP/chongwu_mcp` | 宠物医院 MCP 服务器（stdio），`add_pet` / `get_pets` 两个工具 | 5 个 Python 文件 / 约 410 行 | `python -m unittest discover -s tests -t .`（9 个用例） |
| `AnythingLLMMCP/anything_mcp` | AnythingLLM MCP 桥接（streamable HTTP），工作区列表 / 问答 / 上传并向量化 / 向量检索 四个工具 | 7 个 Python 文件 / 约 570 行 | `python -m unittest discover -s tests -t .`（13 个用例） |
| `AnythingLLMWebPage` | 单页上传工具 + 本地代理，把文件上传到 AnythingLLM **并向量化** | 2 个 JS/HTML 文件 / 约 490 行 | `node --test`（11 个用例） |

```text
                ┌──────────────────────────────┐
                │  Agent/qAgent (Textual TUI)  │
                │  core: agent/tools/sessions  │
                │        compact/skills        │
                └───────────────┬──────────────┘
                                │ MCP 客户端（.mcp.json）
        ┌───────────────────────┴───────────────────────┐
        ▼                                               ▼
┌───────────────────────┐                    ┌─────────────────────────┐
│ PetHospital MCP       │                    │ AnythingLLM MCP         │
│ stdio, 2 tools        │                    │ streamable HTTP, 4 tools│
│ → REST :8080/api/v1   │                    │ → AnythingLLM :3001     │
└───────────────────────┘                    └────────────┬────────────┘
                                                          │ REST
                                              ┌───────────▼────────────┐
                                              │ AnythingLLMWebPage     │
                                              │ 浏览器 → 代理 :8080     │
                                              └────────────────────────┘
```

## 分步启动

### 1. qAgent（主程序）

```powershell
cd Agent\qAgent
py -m pip install -r requirements.txt
py main.py                 # 首次运行会自动生成 config.ini 模板
```

首次运行会在当前目录生成 `config.ini`（含占位 Key），界面会提示"填写后重启"。
把 `[LLM] api_key` 换成真实的 DeepSeek Key 后重新启动即可。

常用斜杠命令：`/help`、`/new`、`/resume`、`/save`、`/compact`、`/mcp`、
`/agents`、`/context`、`/quit`。

### 2. 宠物医院 MCP（供 Agent 调用）

```powershell
cd PetHospitalMCP\chongwu_mcp
uv sync                                   # 或 pip install -e .
$env:PET_HOSPITAL_BASE_URL="http://127.0.0.1:8080/api/v1"
uv run python -m pet_hospital_mcp         # stdio 服务，由 MCP 客户端拉起
```

### 3. AnythingLLM MCP

```powershell
cd AnythingLLMMCP\anything_mcp
uv sync
uv run python run.py                      # http://127.0.0.1:8000/mcp
```

### 4. 网页（上传并向量化）

```powershell
cd AnythingLLMWebPage
node server.js                            # http://localhost:8080/upload.html
```

### 5. 在 MCP 客户端里登记

仓库根 `opencode.json` 已给出两份配置：`PetHospital`（`type: local`，stdio）与
`anythingllm`（`type: remote`，`http://127.0.0.1:8000/mcp`）。qAgent 读的是
**工作目录下的 `.mcp.json`**，格式见 `Agent/qAgent/README.md`。

## 配置速查

密钥统一走环境变量 / 就近的 `.env`（各目录都有 `.env.example` 或
`config.ini.example` 可复制）：

| 变量 | 被谁使用 | 必填 |
| --- | --- | --- |
| `DEEPSEEK_API_KEY` | Project1 / Project2 / qAgent | 是 |
| `BAIDU_SEARCH_API_KEY` | qAgent 的 `searchWeb` | 否（缺了只影响该工具） |
| `PET_HOSPITAL_BASE_URL` / `PET_HOSPITAL_TIMEOUT` / `PET_HOSPITAL_RETRIES` | 宠物医院 MCP | 否（有默认值） |
| `ANYTHINGLLM_BASE_URL` / `ANYTHINGLLM_API_KEY` | AnythingLLM MCP、网页代理 | Key 必填 |
| `MCP_HOST` / `MCP_PORT` | AnythingLLM MCP 监听地址 | 否 |

`.env`、`config.ini`、`*.mcp.json` 都在 `.gitignore` 里，不会误提交。

## 一体化验证

四条命令覆盖全部可自动验证的部分（都不需要外网，用假客户端 / MockTransport /
假上游）：

```powershell
cd Agent\qAgent;                     python -m unittest discover -s tests -t . -v   # 36
cd PetHospitalMCP\chongwu_mcp;       python -m unittest discover -s tests -t . -v   # 9
cd AnythingLLMMCP\anything_mcp;      python -m unittest discover -s tests -t . -v   # 13
cd AnythingLLMWebPage;               node --test                                   # 11
```

CI（`.github/workflows/ci.yml`）四个 job：三套 Python 单测 + `compileall`，以及
网页的 `node --test`（在 127.0.0.1 随机端口上自起代理与假上游，不依赖外部服务）。

## 文档索引

- 顶层（本文件）：模块地图、启动顺序、配置与验证
- `Agent/qAgent/README.md`：事件协议、分层职责、工具清单、护栏/日志、自测
- `Agent/qAgent/AGENT.md`：项目规则文件示例（启动时注入会话）
- `Agent/Project2/README.md`：三个递进版本的工具与架构
- `PetHospitalMCP/chongwu_mcp/README.md`：安装、环境变量、错误码
- `PetHospitalMCP/chongwu_mcp/mcp.md`：设计说明与"与早期计划的差异"
- `AnythingLLMMCP/README.md`：四个工具、错误语义、接入方式
- `AnythingLLMMCP/anything_mcp/MVP_DEVELOPMENT_PLAN.md`：设计取舍与验收清单
- `AnythingLLMWebPage/README.md`：三步上传流程、代理接口、安全措施

## 仓库约定

- 只保留一份可发布代码：任何"工作副本"都已清理，避免同名文件漂移；
- 文档里的命令、文件名、数字必须与代码一致（改代码时同批改文档）；
- 不提交密钥、运行产物（`.agents/`、`__pycache__`、`.venv/`、`*.egg-info`）。
