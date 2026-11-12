# 宠物医院 MCP Server — 设计说明

> 本文描述**已实现**的行为，与 `src/pet_hospital_mcp/__init__.py` 保持一致；
> 安装、配置与运行步骤见同目录 `README.md`。

## 协议与 SDK

- MCP Python SDK `>= 2.0`（`mcp[cli]`），核心类 `from mcp.server import MCPServer`
  （v1 的 `FastMCP` 在新版本中已不再是入口），工具装饰器仍是 `@mcp.tool()`；
- 传输：**stdio**（由 MCP 客户端以子进程方式拉起），因此日志只能写 stderr；
- 错误：`from mcp.server.mcpserver.exceptions import ToolError`。

```python
from mcp.server import MCPServer

mcp = MCPServer("PetHospital")

@mcp.tool()
def get_pets(...) -> dict: ...
```

## 工具清单（2 个）

| 工具 | 作用 | 端点 |
| --- | --- | --- |
| `add_pet` | 新建宠物档案（非幂等） | `POST /pets` |
| `get_pets` | 按条件查档，至少给一个过滤条件 | `GET /pets`、`GET /pets/search`、`GET /pets/by-{dimension}` |

> 首期只规划了 `get_pets`，`add_pet` 随后补上；现在两者都在 `list_tools` 里可见，
> 且都有完整 docstring 与参数约束。

## 参数约束

- `add_pet` 必填 `ownerName`（≤50 字）、`ownerPhone`（≤20）、`disease`（≤200）、
  `doctor`（≤50），可选 `name` / `species` / `status`；
- `get_pets` 全部可选，但**至少一个非 `None`**：`species`、`page`(≥1)、
  `pageSize`(1–100)、`sort`、`ownerName`、`ownerPhone`、`doctor`、`disease`、
  `status`、`keyword`；
- 校验失败抛 `ToolError`，`code = VALIDATION_ERROR`。

## 路由规则（`get_pets`）

| 条件 | 端点 |
| --- | --- |
| 给了 `keyword` | `GET /pets/search?keyword=...` |
| 只给一个维度筛选，且无 `page`/`pageSize`/`sort` | `GET /pets/by-{species|owner|doctor|disease|status}` |
| 其他（多维度 / 排序 / 分页） | `GET /pets?...` |

维度 → 端点的映射：`ownerName` 与 `ownerPhone` 都走 `by-owner`（后端按电话还是
姓名匹配由后端决定，工具只负责把值传过去）。

## 返回结构

```json
{ "pets": [ { "id": 1, "name": "豆豆", "totalCost": 0, "visitCount": 0, "...": "..." } ],
  "total": 12, "page": 1, "pageSize": 10 }
```

`add_pet` 返回 `{ "pet": {...}, "code": 201, "message": "success" }`。

## 可靠性

| 机制 | 实现 |
| --- | --- |
| 超时 | `PET_HOSPITAL_TIMEOUT`（默认 10 秒） |
| 重试 | `PET_HOSPITAL_RETRIES`（默认 2）；传输错误所有方法重试，5xx 只重试 GET；退避 `0.3s × 第 n 次` |
| 日志 | stderr，一行一次：方法 / 路径 / 状态码 / 耗时 / `attempt n/m` |
| 错误码 | `UPSTREAM_UNREACHABLE`、`UPSTREAM_TIMEOUT`、`UPSTREAM_HTTP_ERROR`、`UPSTREAM_BAD_PAYLOAD`、`VALIDATION_ERROR` |
| 响应体 | 不整段透传：JSON 取 `message`/`msg`，否则截断 160 字 |

## 配置（MCP 客户端登记）

见 `README.md` 的 `mcpServers` 示例；仓库根与 `PetHospitalMCP/opencode.json`
各有一份等价配置（stdio、`uv run python -m pet_hospital_mcp`）。

## 验证

```bash
python -m unittest discover -s tests -t . -v   # 9 个用例，不需要后端
python src/test_mcp_client.py                  # 端到端，需要后端已启动
```

## 与早期计划的差异

- 早期计划里的 `D:\LLM\PetHospitalMCP\.opencode\opencode.jsonc` 并不存在，
  实际配置在 `PetHospitalMCP/opencode.json` 与仓库根 `opencode.json`；
- 早期计划写的 `[tool.uv.scripts] pet-hospital-mcp = "src.server:mcp.run()"`
  不是合法配置，实际入口是 `[project.scripts] pet-hospital-mcp =
  "pet_hospital_mcp:main"`（等价于 `python -m pet_hospital_mcp`）；
- 早期只做 `get_pets`，现已补 `add_pet`、重试、日志、错误码与单元测试。
