# Pet Hospital MCP Server

宠物医院管理系统的 MCP Server（stdio 传输），把本机宠物医院后端的 REST 接口
封装成两个模型可调用的工具：`add_pet`（建档）、`get_pets`（按条件查档）。

## 快速开始

```bash
uv sync                                  # 或 pip install -e .
pet-hospital-mcp                         # 安装后的命令入口
uv run python -m pet_hospital_mcp        # 不安装，直接以模块运行
```

在 MCP 客户端里登记（VS Code / opencode 的 `mcpServers` 写法）：

```json
{
  "mcpServers": {
    "pet-hospital": {
      "command": "uv",
      "args": ["run", "python", "-m", "pet_hospital_mcp"],
      "cwd": "D:\\LLM\\PetHospitalMCP\\chongwu_mcp",
      "env": { "PET_HOSPITAL_BASE_URL": "http://127.0.0.1:8080/api/v1" }
    }
  }
}
```

## 配置（全部走环境变量）

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `PET_HOSPITAL_BASE_URL` | `http://127.0.0.1:8080/api/v1` | 后端 REST 根地址 |
| `PET_HOSPITAL_TIMEOUT` | `10` | 单次请求超时（秒） |
| `PET_HOSPITAL_RETRIES` | `2` | 失败重试次数（总尝试 = 1 + 该值） |
| `PET_HOSPITAL_LOG_LEVEL` | `INFO` | 调用日志级别（`DEBUG` 可看到每次重试细节） |

模板见同目录 `.env.example`（复制成 `.env` 或直接设成环境变量都行）。

调用工具前需要先启动宠物医院后端服务。

## 可靠性设计

| 机制 | 行为 |
| --- | --- |
| 超时 | 每次请求 `PET_HOSPITAL_TIMEOUT` 秒，超时后按重试策略处理 |
| 重试 | 传输层错误（连不上、连接被重置）**所有方法**都重试；HTTP 5xx **只重试幂等的 GET**，避免重复建档；退避 `0.3s × 第几次尝试` |
| 日志 | 一行一次调用：方法、路径、状态码、耗时、`attempt n/m`；写 **stderr**（stdio 服务器的 stdout 是协议通道，不能污染） |
| 错误语义 | 失败抛 `ToolError`，消息体是 JSON，便于模型判断"该重试 / 该改参数 / 该报后端故障" |

错误码：

| code | 触发条件 | 模型该怎么做 |
| --- | --- | --- |
| `UPSTREAM_UNREACHABLE` | 连接失败，重试耗尽 | 提示用户后端未启动或地址不对，别改参数硬试 |
| `UPSTREAM_TIMEOUT` | 超时，重试耗尽 | 稍后重试或确认后端是否卡住 |
| `UPSTREAM_HTTP_ERROR` | 4xx / 5xx（含 `status` 字段） | 4xx 多数是参数问题，按 `detail` 修正后重试 |
| `UPSTREAM_BAD_PAYLOAD` | 返回非 JSON 或结构不符合约定 | 报告后端响应异常，不要重试 |
| `VALIDATION_ERROR` | 缺少必填参数 / 未给任何过滤条件 | 补参数 |

错误示例（`add_pet` 打到一个挂了的路由）：

```json
{"code": "UPSTREAM_HTTP_ERROR", "status": 404, "message": "宠物医院接口返回 HTTP 404（POST /pets）。", "detail": "route not found"}
```

上游响应体**不整段透传**：若响应是 JSON，只取 `message` / `msg` / `error` 字段；
否则取纯文本并截断到 160 字，避免把整页 HTML 塞进模型的上下文。

## 工具

### `get_pets`

查询宠物档案列表，支持多参数筛选。

**参数**（均为可选，但至少要给一个，否则 `VALIDATION_ERROR`）：

| 参数 | 类型 | 说明 |
|------|------|------|
| `species` | string | 按种类筛选 |
| `page` | int ≥ 1 | 页码 |
| `pageSize` | int 1–100 | 每页条数 |
| `sort` | string | 排序方式 |
| `ownerName` | string | 按主人姓名筛选 |
| `ownerPhone` | string | 按主人电话筛选 |
| `doctor` | string | 按主治医生筛选 |
| `disease` | string | 按疾病筛选 |
| `status` | string | 按就诊状态筛选 |
| `keyword` | string | 全文检索关键词 |

**返回结构**：

```json
{ "pets": [], "total": 0, "page": 1, "pageSize": 10 }
```

**端点路由**（同一个工具按参数组合选不同后端接口，减少模型需要记的端点）：

- 给了 `keyword` → `GET /pets/search`
- 只给一个维度、且没有分页/排序 → `GET /pets/by-{species|owner|doctor|disease|status}`
- 其余（多维度 / 排序 / 分页） → `GET /pets`

### `add_pet`

添加新的宠物档案。

**必填**：`ownerName`、`ownerPhone`、`disease`、`doctor`；
**可选**：`name`、`species`、`status`。

**返回结构**：

```json
{ "pet": { "id": 7, "name": "豆豆", "...": "..." }, "code": 201, "message": "created" }
```

**端点**：`POST /pets`（非幂等，所以 5xx 不自动重试）。

## 测试

```bash
# 单元测试：替换 httpx.request，不需要后端，也不需要网络
python -m unittest discover -s tests -t . -v

# 端到端冒烟：真的拉起 stdio server 并调用工具，需要后端已启动
python src/test_mcp_client.py
```

单元测试覆盖：GET 5xx 重试后成功、POST 5xx 不重试、超时耗尽、连接失败、
错误 detail 截断（不透传整段响应体）、非 JSON 响应、缺过滤参数的
`VALIDATION_ERROR`、返回结构格式化。

## 目录结构

```text
chongwu_mcp/
├── pyproject.toml
├── src/
│   ├── pet_hospital_mcp/__init__.py   # MCP 实例、两个工具、请求层
│   ├── pet_hospital_mcp/__main__.py   # python -m pet_hospital_mcp
│   ├── server.py                      # 兼容旧入口
│   └── test_mcp_client.py             # 端到端冒烟（需后端）
└── tests/
    └── test_tools.py                   # 单元测试
```

## 依赖

- Python 3.10+
- `mcp >= 2.0`（使用 `MCPServer` / `ToolError` 这一代 API）
- `httpx >= 0.27`、`pydantic >= 2.0`
