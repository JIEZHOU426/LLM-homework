# Pet Hospital MCP Server

宠物医院管理系统 MCP Server，提供 `get_pets` 和 `add_pet` 工具。

## 安装

```bash
uv sync
```

## 使用

```bash
uv run python src/server.py
```

或使用 MCP Inspector：

```bash
uv run mcp dev src/server.py
```

安装为命令后也可以直接运行：

```bash
uv run pet-hospital-mcp
```

## 配置

后端服务地址通过环境变量 `PET_HOSPITAL_BASE_URL` 配置，默认
`http://127.0.0.1:8080/api/v1`。调用工具前需要先启动宠物医院后端服务。

```bash
set PET_HOSPITAL_BASE_URL=http://127.0.0.1:8080/api/v1
```

## 工具

### `get_pets`

查询宠物档案列表，支持多参数筛选。

**参数**（均为可选，至少提供一个）：

| 参数 | 类型 | 说明 |
|------|------|------|
| `species` | string | 按种类筛选 |
| `page` | int | 页码 |
| `pageSize` | int | 每页条数 |
| `sort` | string | 排序方式 |
| `ownerName` | string | 按主人姓名筛选 |
| `ownerPhone` | string | 按主人电话筛选 |
| `doctor` | string | 按主治医生筛选 |
| `disease` | string | 按疾病筛选 |
| `status` | string | 按就诊状态筛选 |
| `keyword` | string | 全文检索关键词 |

**返回结构**：

```json
{
  "pets": [...],
  "total": 0,
  "page": 1,
  "pageSize": 10
}
```

**API 端点映射**：

- 全文检索 → `GET /api/v1/pets/search`
- 单一维度过滤 → `GET /api/v1/pets/by-{dimension}`
- 多维度组合/排序/分页 → `GET /api/v1/pets`

### `add_pet`

添加新的宠物档案。

**必填参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| `ownerName` | string | 主人姓名 |
| `ownerPhone` | string | 主人电话 |
| `disease` | string | 疾病名称 |
| `doctor` | string | 主治医生 |

**可选参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| `name` | string | 宠物名称 |
| `species` | string | 宠物种类（如"犬"、"猫"） |
| `status` | string | 就诊状态（如"住院中"、"已康复"） |

**返回结构**：

```json
{
  "pet": { "id": "...", "name": "...", ... },
  "code": 201,
  "message": "success"
}
```

**API 端点**：`POST /api/v1/pets`

## 依赖

- Python 3.10+
- mcp[cli] >= 2.0.0
- httpx >= 0.27.0
- pydantic >= 2.0.0
