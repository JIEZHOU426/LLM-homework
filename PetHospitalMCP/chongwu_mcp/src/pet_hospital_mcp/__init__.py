import os
from typing import Annotated, Optional

import httpx
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

mcp = MCPServer("PetHospital")

BASE_URL = os.getenv(
    "PET_HOSPITAL_BASE_URL", "http://127.0.0.1:8080/api/v1"
).rstrip("/")


def _has_filter(params: dict) -> bool:
    return any(v is not None for v in params.values())


def _build_query_params(params: dict) -> dict:
    return {k: v for k, v in params.items() if v is not None}


def _request(method: str, path: str, **kwargs) -> httpx.Response:
    try:
        response = httpx.request(method, f"{BASE_URL}{path}", timeout=10, **kwargs)
    except httpx.RequestError as exc:
        raise ToolError(f"无法连接宠物医院后端 {BASE_URL}: {exc}") from exc
    if response.is_error:
        raise ToolError(
            f"宠物医院接口错误: HTTP {response.status_code} - {response.text}"
        )
    return response


@mcp.tool()
def add_pet(
    ownerName: Annotated[str, Field(max_length=50)] = Field(..., description="主人姓名"),
    ownerPhone: Annotated[str, Field(max_length=20)] = Field(..., description="主人电话"),
    disease: Annotated[str, Field(max_length=200)] = Field(..., description="疾病名称"),
    doctor: Annotated[str, Field(max_length=50)] = Field(..., description="主治医生"),
    name: Optional[str] = Field(None, description="宠物名称"),
    species: Optional[str] = Field(None, description="宠物种类（如犬、猫）"),
    status: Optional[str] = Field(None, description="就诊状态（如住院中、已康复）"),
) -> dict:
    """
    添加新的宠物档案。

    必填参数：ownerName、ownerPhone、disease、doctor。
    可选参数：name、species、status。

    返回结构：
    - pet: 创建的宠物信息，包含 id、name、species、ownerName、ownerPhone、disease、doctor、status、totalCost、visitCount
    - code: 状态码
    - message: 消息
    """
    payload = {
        "ownerName": ownerName,
        "ownerPhone": ownerPhone,
        "disease": disease,
        "doctor": doctor,
    }
    if name is not None:
        payload["name"] = name
    if species is not None:
        payload["species"] = species
    if status is not None:
        payload["status"] = status

    response = _request("POST", "/pets", json=payload)
    return _format_add_response(response.json())


@mcp.tool()
def get_pets(
    species: Optional[Annotated[str, Field(max_length=50)]] = None,
    page: Optional[Annotated[int, Field(ge=1)]] = None,
    pageSize: Optional[Annotated[int, Field(ge=1)]] = None,
    sort: Optional[str] = None,
    ownerName: Optional[str] = None,
    ownerPhone: Optional[str] = None,
    doctor: Optional[str] = None,
    disease: Optional[str] = None,
    status: Optional[str] = None,
    keyword: Optional[str] = None,
) -> dict:
    """
    查询宠物医院档案列表，支持多参数筛选。

    至少需要提供一个过滤参数。不允许无条件全量查询。

    参数说明：
    - species: 按种类筛选（如"犬"、"猫"）
    - page: 页码，默认1
    - pageSize: 每页条数，默认10
    - sort: 排序方式（如"最新建档"、"总花费从高到低"）
    - ownerName: 按主人姓名筛选
    - ownerPhone: 按主人电话筛选
    - doctor: 按主治医生筛选
    - disease: 按疾病筛选
    - status: 按就诊状态筛选（如"住院中"、"已康复"）
    - keyword: 全文检索关键词

    返回结构：
    - pets: 宠物列表，每只宠物包含 id、name、species、ownerName、ownerPhone、disease、doctor、status、totalCost、visitCount
    - total: 总数
    - page: 页码
    - pageSize: 每页条数
    """
    single_dim_filters = {
        "species": species,
        "ownerName": ownerName,
        "ownerPhone": ownerPhone,
        "doctor": doctor,
        "disease": disease,
        "status": status,
    }
    all_params = {
        "species": species,
        "page": page,
        "pageSize": pageSize,
        "sort": sort,
        "ownerName": ownerName,
        "ownerPhone": ownerPhone,
        "doctor": doctor,
        "disease": disease,
        "status": status,
        "keyword": keyword,
    }

    if not _has_filter(all_params):
        raise ToolError("至少需要提供一个过滤参数")

    if keyword is not None:
        params = _build_query_params({"keyword": keyword})
        response = _request("GET", "/pets/search", params=params)
        return _format_response(response.json())

    provided_single = {k: v for k, v in single_dim_filters.items() if v is not None}

    if len(provided_single) == 1 and page is None and pageSize is None and sort is None:
        dim, val = next(iter(provided_single.items()))
        endpoint_map = {
            "species": "species",
            "ownerName": "owner",
            "ownerPhone": "owner",
            "doctor": "doctor",
            "disease": "disease",
            "status": "status",
        }
        endpoint = endpoint_map[dim]
        params = _build_query_params({dim: val})
        response = _request("GET", f"/pets/by-{endpoint}", params=params)
        return _format_response(response.json())

    params = _build_query_params(all_params)
    response = _request("GET", "/pets", params=params)
    return _format_response(response.json())


def _format_response(data: dict) -> dict:
    inner = data.get("data", data)
    return {
        "pets": inner.get("items", inner.get("pets", [])),
        "total": inner.get("total", 0),
        "page": inner.get("page", 1),
        "pageSize": inner.get("pageSize", 10),
    }


def _format_add_response(data: dict) -> dict:
    inner = data.get("data", data)
    return {
        "pet": inner,
        "code": data.get("code", 201),
        "message": data.get("message", "success"),
    }


def main() -> None:
    mcp.run()
