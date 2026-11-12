"""宠物医院 MCP 服务端。

以 MCP 协议对外暴露两个业务工具（建档、按条件查档），底层调用本机宠物医院
后端 REST 接口。工程约定：

- **超时**：``PET_HOSPITAL_TIMEOUT``（秒，默认 10）；
- **重试**：``PET_HOSPITAL_RETRIES``（默认 2，即最多 3 次尝试）。传输层错误
  对所有方法重试，HTTP 5xx 只对幂等的 GET 重试，避免重复建档；
- **调用日志**：写 stderr（stdio 服务器的 stdout 属于协议通道，绝不能污染），
  一行一次调用：方法、路径、状态码、耗时、第几次尝试；
- **错误语义**：失败一律抛 ``ToolError``，消息体是 JSON
  ``{"code": ..., "message": ..., "status": ..., "detail": ...}``，
  上游响应体只取 ``message`` 字段或截断后的文本，不整段透传。
"""

import json
import logging
import os
import sys
import time
from typing import Annotated, Optional

import httpx
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

mcp = MCPServer("PetHospital")

BASE_URL = os.getenv(
    "PET_HOSPITAL_BASE_URL", "http://127.0.0.1:8080/api/v1"
).rstrip("/")
TIMEOUT = float(os.getenv("PET_HOSPITAL_TIMEOUT", "10"))
RETRIES = max(0, int(os.getenv("PET_HOSPITAL_RETRIES", "2")))
BACKOFF_SECONDS = 0.3
_ERROR_SNIPPET_MAX = 160

logger = logging.getLogger("pet_hospital_mcp")
if not logger.handlers:  # 库被 import 时也能输出，且不重复添加 handler
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    logger.addHandler(handler)
    logger.setLevel(os.getenv("PET_HOSPITAL_LOG_LEVEL", "INFO").upper())
    logger.propagate = False

# 错误码：调用方（模型）据此判断该重试、改参数还是报告后端故障
ERROR_UNREACHABLE = "UPSTREAM_UNREACHABLE"
ERROR_TIMEOUT = "UPSTREAM_TIMEOUT"
ERROR_HTTP = "UPSTREAM_HTTP_ERROR"
ERROR_BAD_PAYLOAD = "UPSTREAM_BAD_PAYLOAD"
ERROR_VALIDATION = "VALIDATION_ERROR"


def _tool_error(
    code: str,
    message: str,
    *,
    status: int | None = None,
    detail: str | None = None,
) -> ToolError:
    """构造结构化错误：模型能读到 code，用户能看到可读消息。"""

    payload: dict = {"code": code, "message": message}
    if status is not None:
        payload["status"] = status
    if detail:
        payload["detail"] = detail
    return ToolError(json.dumps(payload, ensure_ascii=False))


def _error_detail(response: httpx.Response) -> str:
    """只取上游的 message 字段或截断文本，绝不整段透传响应体。"""

    try:
        body = response.json()
    except ValueError:
        body = None
    if isinstance(body, dict):
        for key in ("message", "msg", "error", "detail"):
            value = body.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()[:_ERROR_SNIPPET_MAX]
    text = (response.text or "").strip().replace("\n", " ")
    if not text:
        return ""
    return text[:_ERROR_SNIPPET_MAX] + ("…" if len(text) > _ERROR_SNIPPET_MAX else "")


def _has_filter(params: dict) -> bool:
    return any(v is not None for v in params.values())


def _build_query_params(params: dict) -> dict:
    return {k: v for k, v in params.items() if v is not None}


def _request(method: str, path: str, **kwargs) -> httpx.Response:
    """带超时、重试与调用日志的请求；失败抛出结构化 ToolError。"""

    url = f"{BASE_URL}{path}"
    attempts = RETRIES + 1
    idempotent = method.upper() == "GET"

    for attempt in range(1, attempts + 1):
        started = time.perf_counter()
        try:
            response = httpx.request(method, url, timeout=TIMEOUT, **kwargs)
        except httpx.TimeoutException as exc:
            elapsed = int((time.perf_counter() - started) * 1000)
            logger.warning(
                "%s %s timeout after %d ms (attempt %d/%d): %s",
                method, path, elapsed, attempt, attempts, exc,
            )
            if attempt < attempts:
                time.sleep(BACKOFF_SECONDS * attempt)
                continue
            raise _tool_error(
                ERROR_TIMEOUT,
                f"宠物医院后端 {BASE_URL} 响应超时（{TIMEOUT:g} 秒，已尝试 "
                f"{attempt} 次）。请稍后重试或确认后端是否卡住。",
            ) from exc
        except httpx.RequestError as exc:
            elapsed = int((time.perf_counter() - started) * 1000)
            logger.warning(
                "%s %s connect error after %d ms (attempt %d/%d): %s",
                method, path, elapsed, attempt, attempts, exc,
            )
            if attempt < attempts:
                time.sleep(BACKOFF_SECONDS * attempt)
                continue
            raise _tool_error(
                ERROR_UNREACHABLE,
                f"无法连接宠物医院后端 {BASE_URL}（已尝试 {attempt} 次）。"
                "请确认后端已启动、地址与端口正确（PET_HOSPITAL_BASE_URL）。",
            ) from exc

        elapsed = int((time.perf_counter() - started) * 1000)
        logger.info(
            "%s %s -> %s (%d ms, attempt %d/%d)",
            method, path, response.status_code, elapsed, attempt, attempts,
        )

        if response.is_error:
            detail = _error_detail(response)
            if response.status_code >= 500 and idempotent and attempt < attempts:
                logger.warning(
                    "%s %s returned %s, retrying (attempt %d/%d)",
                    method, path, response.status_code, attempt, attempts,
                )
                time.sleep(BACKOFF_SECONDS * attempt)
                continue
            raise _tool_error(
                ERROR_HTTP,
                f"宠物医院接口返回 HTTP {response.status_code}（{method} {path}）。",
                status=response.status_code,
                detail=detail,
            )
        return response

    # 理论上到不了这里：循环内所有路径都已 return 或 raise
    raise _tool_error(ERROR_UNREACHABLE, f"请求失败：{method} {path}")


def _json_body(response: httpx.Response) -> dict:
    """解析 JSON 响应；非 JSON 或非对象时给出 BAD_PAYLOAD 错误。"""

    try:
        body = response.json()
    except ValueError as exc:
        raise _tool_error(
            ERROR_BAD_PAYLOAD,
            "宠物医院接口返回的不是 JSON，无法解析。",
            status=response.status_code,
            detail=(response.text or "").strip()[:_ERROR_SNIPPET_MAX],
        ) from exc
    if not isinstance(body, dict):
        raise _tool_error(
            ERROR_BAD_PAYLOAD,
            f"宠物医院接口返回的 JSON 顶层应为对象，实际是 {type(body).__name__}。",
            status=response.status_code,
        )
    return body


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
    return _format_add_response(_json_body(response))


@mcp.tool()
def get_pets(
    species: Optional[Annotated[str, Field(max_length=50)]] = None,
    page: Optional[Annotated[int, Field(ge=1)]] = None,
    pageSize: Optional[Annotated[int, Field(ge=1, le=100)]] = None,
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
    - pageSize: 每页条数，默认10，上限100
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
        raise _tool_error(
            ERROR_VALIDATION,
            "至少需要提供一个过滤参数（例如 ownerName、species、keyword），"
            "不支持无条件全量查询。",
        )

    if keyword is not None:
        params = _build_query_params({"keyword": keyword})
        response = _request("GET", "/pets/search", params=params)
        return _format_response(_json_body(response))

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
        return _format_response(_json_body(response))

    params = _build_query_params(all_params)
    response = _request("GET", "/pets", params=params)
    return _format_response(_json_body(response))


def _format_response(data: dict) -> dict:
    inner = data.get("data", data)
    if not isinstance(inner, dict):
        raise _tool_error(
            ERROR_BAD_PAYLOAD,
            "宠物医院接口返回的 data 字段不是对象。",
            detail=str(type(inner).__name__),
        )
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
