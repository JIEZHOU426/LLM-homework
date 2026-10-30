# 宠物医院管理系统 MCP Server — 首期：get_pets 工具开发

## 核心变更（相对于上期）
- **语言**：Python 3.10+（非 Go）
- **范围**：仅实现 `get_pets` 一个 Tool，不做 Resources/Prompts/其他工具
- **目标**：列出宠物档案，支持多参数筛选

## 协议与 SDK

- **MCP 协议版本**：`2026-07-28`（最新版）
- **SDK**：`mcp` Python SDK v2.x（`pip install "mcp[cli]"`），v2 原生支持 2026-07-28 规范
- **核心类**：`from mcp.server import MCPServer`（v1 的 `FastMCP` 已废弃）
- **装饰器**：`@mcp.tool()` 语法不变
- **传输层**：stdio

```python
from mcp.server import MCPServer

mcp = MCPServer("PetHospital")

@mcp.tool()
def get_pets(...) -> dict:
    """..."""
```

## 项目结构

```
D:\LLM\PetHospitalMCP\chongwu_mcp\
├── .opencode\
│   └── opencode.jsonc      ← 已有（需更新配置指向 pet-hospital-mcp）
├── src\
│   └── server.py           ← 主服务器文件
├── pyproject.toml            ← 依赖管理（使用 uv）
└── README.md
```

## 依赖

```toml
# pyproject.toml
[project]
name = "pet-hospital-mcp"
requires-python = ">=3.10"
dependencies = [
    "mcp[cli]>=2.0.0",
    "httpx>=0.27.0",
    "pydantic>=2.0.0",
]

[tool.uv.scripts]
pet-hospital-mcp = "src.server:mcp.run()"
```

## 宿主系统 API

- **基础 URL**：`http://127.0.0.1:8080/api/v1`
- **核心端点**：`GET /api/v1/pets` — 查询宠物列表

`GET /api/v1/pets` 支持的查询参数（全部来自 API 文档）：

| 参数 | 类型 | 说明 |
|------|------|------|
| `species` | string | 按种类筛选（如"犬"、"猫"） |
| `page` | int | 页码，默认1 |
| `pageSize` | int | 每页条数，默认10 |
| `sort` | string | 排序方式（如"最新建档"、"总花费从高到低"） |
| `ownerName` | string | 按主人姓名筛选（通过 `/pets/by-owner`） |
| `ownerPhone` | string | 按主人电话筛选 |
| `doctor` | string | 按主治医生筛选（通过 `/pets/by-doctor`） |
| `disease` | string | 按疾病筛选（通过 `/pets/by-disease`） |
| `status` | string | 按就诊状态筛选（如"住院中"、"已康复"） |
| `keyword` | string | 全文检索关键词（通过 `/pets/search`） |

## get_pets Tool 设计要求

1. **函数签名**：使用 Python type hints 作为 MCP inputSchema
2. **参数说明**：
   - 所有过滤参数均为 **可选**（Optional）
   - 使用 `pydantic` 或 `Annotated` 定义参数约束
   - 至少一个过滤参数必须提供（不允许无条件全量查询）
3. **行为逻辑**：
   - 根据传入参数调用对应的宿主 API 端点
   - 单一维度过滤走 `/pets/by-{dimension}` 端点
   - 多维度组合或通用排序/分页走 `/pets` 端点
   - 全文检索走 `/pets/search`
   - 未知参数组合返回错误信息
4. **返回值**：
   - 结构化 JSON，包含 `pets`（列表）、`total`（总数）、`page`（页码）、`pageSize`（每页）
   - 每只宠物包含：id、name、species、ownerName、ownerPhone、disease、doctor、status、totalCost、visitCount
5. **错误处理**：
   - HTTP 错误转换为 MCP 工具错误
   - 无匹配结果返回空列表而非错误
6. **Docstring**：清晰描述工具功能、参数含义和返回结构

## 配置文件更新

更新 `D:\LLM\PetHospitalMCP\chongwu_mcp\.opencode\opencode.jsonc`：
```jsonc
{
  "mcp": {
    "servers": {
      "Bazi": {
        "command": "npx",
        "args": ["bazi-mcp"],
        "cwd": "D:\\makeai"
      },
      "PetHospital": {
        "command": "python",
        "args": ["-m", "pet_hospital_mcp"],
        "cwd": "D:\\LLM\\PetHospitalMCP\\chongwu_mcp"
      }
    }
  }
}
```

## 完成标准

1. `pip install "mcp[cli]"` 安装成功
2. `python src/server.py` 以 stdio 模式启动无报错
3. `mcp dev src/server.py` 能正常启动 MCP Inspector
4. 调用 `get_pets` 工具能正确从 `http://127.0.0.1:8080/api/v1/pets` 获取并返回过滤后的宠物数据
