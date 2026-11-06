"""MCP client integration.

Reads ``.mcp.json`` from the current workspace, connects each configured MCP
Server (stdio or Streamable HTTP), discovers tools via ``list_tools()`` and
registers them in the shared :class:`ToolRegistry` so the LLM can call them
like any local Function Calling tool. Call results (text, structured data and
errors) are normalized into plain strings before being handed back to the
model.
"""

from __future__ import annotations

import asyncio
import json
import re
from collections import Counter
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Mapping

from mcp import Client, StdioServerParameters
from mcp_types import (
    CallToolResult,
    EmbeddedResource,
    ImageContent,
    TextContent,
)

from .base import Tool, ToolSpec
from .common import json_error
from .registry import ToolRegistry

MCP_CONFIG_FILENAME = ".mcp.json"

HTTP_TYPES = {
    "streamable_http",
    "streamable-http",
    "streamablehttp",
    "http",
    "http_stream",
    "url",
}
STDIO_TYPES = {"stdio", "local", "command"}
SSE_TYPES = {"sse", "streamable_sse"}

_PREFIX_SAFE = re.compile(r"[^A-Za-z0-9_-]")


def _describe_exception(exc: BaseException) -> str:
    """Flatten ExceptionGroups (e.g. from anyio transports) into one line."""
    sub = getattr(exc, "exceptions", None)
    if isinstance(sub, tuple) and sub:
        return "; ".join(_describe_exception(item) for item in sub)
    text = str(exc).strip()
    if not text:
        return type(exc).__name__
    name = type(exc).__name__
    return f"{name}: {text}" if name not in text else text


@dataclass(frozen=True, slots=True)
class McpServerStatus:
    """Connection outcome for one server entry in ``.mcp.json``."""

    name: str
    status: str  # connected | failed | skipped
    tool_count: int = 0
    error: str = ""


@dataclass
class McpConnectReport:
    """Result of a full MCP connect pass, consumed by front-ends."""

    config_path: Path
    servers: list[McpServerStatus]

    @property
    def configured(self) -> bool:
        return self.config_path.exists() and any(
            entry.status != "skipped" for entry in self.servers
        )

    def summary(self) -> str:
        """Render a markdown summary for display in the chat view."""
        if not self.config_path.exists():
            return f"未找到 `{self.config_path.name}`，MCP 功能未启用。"
        lines: list[str] = []
        for entry in self.servers:
            if entry.status == "connected":
                lines.append(f"- **{entry.name}**：已连接（{entry.tool_count} 个工具）")
            elif entry.status == "skipped":
                lines.append(f"- {entry.error}")
            else:
                lines.append(f"- **{entry.name}**：连接失败 —— {entry.error}")
        return f"### MCP 连接\n\n" + "\n".join(lines)


class McpTool(Tool):
    """A tool backed by a remote MCP server call."""

    def __init__(
        self,
        spec: ToolSpec,
        manager: "McpToolManager",
        server_name: str,
        tool_name: str,
    ) -> None:
        self._spec = spec
        self._manager = manager
        self._server_name = server_name
        self._tool_name = tool_name

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    def run(self, arguments: Mapping[str, Any]) -> str:
        raise RuntimeError("MCP 工具必须通过异步接口调用")

    async def run_async(self, arguments: Mapping[str, Any]) -> str:
        return await self._manager.call_tool(self._spec.name, arguments)


class McpToolManager:
    """Owns MCP connections and the server/tool name mapping."""

    def __init__(self, request_timeout: float = 120.0, connect_timeout: float = 20.0) -> None:
        self._request_timeout = max(request_timeout, 1.0)
        self._connect_timeout = max(connect_timeout, 1.0)
        self._clients: dict[str, Client] = {}
        self._tool_specs: dict[str, list[ToolSpec]] = {}
        self._statuses: dict[str, McpServerStatus] = {}
        self._exposed: dict[str, list[str]] = {}
        self._exposed_specs: dict[str, ToolSpec] = {}

        # exposed tool name -> (server name, real tool name)
        self._routing: dict[str, tuple[str, str]] = {}

    def has_tools(self) -> bool:
        return bool(self._tool_specs)

    @property
    def routing(self) -> Mapping[str, tuple[str, str]]:
        return self._routing

    def snapshot(self) -> list[dict[str, Any]]:
        """Sidebar-friendly view: every server with its exposed tools."""

        servers: list[dict[str, Any]] = []
        seen: set[str] = set()
        for name, client in self._clients.items():
            seen.add(name)
            exposed = self._exposed.get(name, [])
            routing = self._routing
            tools = []
            for exposed_name in exposed:
                spec = self._exposed_specs.get(exposed_name)
                description = spec.description if spec else ""
                tools.append(
                    {
                        "name": exposed_name,
                        "description": description.splitlines()[0]
                        if description
                        else "",
                    }
                )
            servers.append(
                {
                    "name": name,
                    "status": "connected",
                    "tool_count": len(exposed),
                    "tools": tools,
                    "error": "",
                    "detail": "流式连接已建立" if routing else "",
                }
            )
            if client is None:  # pragma: no cover - defensive
                servers[-1]["status"] = "failed"
        for name, status in self._statuses.items():
            if name in seen:
                continue
            servers.append(
                {
                    "name": name,
                    "status": status.status,
                    "tool_count": 0,
                    "tools": [],
                    "error": status.error,
                    "detail": "",
                }
            )
        return servers

    async def connect_from_config(self, workspace_root: Path) -> McpConnectReport:
        """Connect every server in ``<workspace_root>/.mcp.json``.

        A failing server is reported and skipped; other servers keep working.
        """
        config_path = Path(workspace_root) / MCP_CONFIG_FILENAME
        report = McpConnectReport(config_path=config_path, servers=[])

        if not config_path.exists():
            report.servers.append(
                McpServerStatus(
                    name="",
                    status="skipped",
                    error=f"未找到 `{config_path.name}`，MCP 功能未启用。",
                )
            )
            return report

        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            report.servers.append(
                McpServerStatus(name="", status="skipped", error=f"读取 .mcp.json 失败: {exc}")
            )
            return report

        servers = data.get("mcpServers")
        if not isinstance(servers, dict):
            report.servers.append(
                McpServerStatus(
                    name="",
                    status="skipped",
                    error=".mcp.json 中缺少 mcpServers 配置，MCP 功能未启用。",
                )
            )
            return report

        for name, cfg in servers.items():
            status = await self._connect_with_timeout(name, cfg)
            report.servers.append(status)
        return report

    async def _connect_with_timeout(self, name: str, cfg: Any) -> McpServerStatus:
        is_dict = isinstance(cfg, dict)
        has_url = is_dict and bool(cfg.get("url"))
        has_command = is_dict and bool(cfg.get("command"))
        if not (has_url or has_command):
            return McpServerStatus(
                name=name,
                status="failed",
                error="配置缺少 url（HTTP）或 command（stdio）字段",
            )
        try:
            status = await asyncio.wait_for(
                self._connect_server(name, cfg), self._connect_timeout
            )
            self._statuses[name] = status
            return status
        except TimeoutError:
            status = McpServerStatus(
                name=name,
                status="failed",
                error=f"连接超时（{self._connect_timeout:.0f} 秒）",
            )
            self._statuses[name] = status
            return status
        except Exception as exc:  # noqa: BLE001 - connection failures are data
            status = McpServerStatus(
                name=name,
                status="failed",
                error=_describe_exception(exc),
            )
            self._statuses[name] = status
            return status

    async def _connect_server(self, name: str, cfg: Mapping[str, Any]) -> McpServerStatus:
        client = self._build_client(name, cfg)
        await client.__aenter__()
        try:
            listing = await client.list_tools()
        except Exception:
            await self._safe_exit(name, client)
            raise

        specs: list[ToolSpec] = []
        for tool in listing.tools:
            specs.append(
                ToolSpec(
                    name=tool.name,
                    description=tool.description or "",
                    parameters=dict(tool.input_schema or {}),
                )
            )
        self._clients[name] = client
        self._tool_specs[name] = specs
        return McpServerStatus(name=name, status="connected", tool_count=len(specs))

    def _build_client(self, name: str, cfg: Mapping[str, Any]) -> Client:
        server_type = str(cfg.get("type", "") or "").strip().lower()
        if not server_type:
            server_type = "stdio" if "command" in cfg else "http"

        if server_type in HTTP_TYPES or ("url" in cfg and server_type not in SSE_TYPES):
            url = str(cfg["url"]).strip()
            if not url:
                raise ValueError(f"MCP Server '{name}' 的 url 不能为空")
            return Client(url, read_timeout_seconds=self._request_timeout)

        if server_type in STDIO_TYPES or "command" in cfg:
            command = str(cfg.get("command", "")).strip()
            if not command:
                raise ValueError(f"MCP Server '{name}' 的 command 不能为空")
            args = [str(arg) for arg in (cfg.get("args") or [])]
            env = cfg.get("env") if isinstance(cfg.get("env"), dict) else None
            cwd = cfg.get("cwd")
            params = StdioServerParameters(
                command=command,
                args=args,
                env=env,
                cwd=cwd,
            )
            return Client(params, read_timeout_seconds=self._request_timeout)

        raise ValueError(f"MCP Server '{name}' 的传输类型不支持: {server_type}")

    async def _safe_exit(self, name: str, client: Client) -> None:
        try:
            await client.__aexit__(None, None, None)
        except Exception:  # noqa: BLE001 - cleanup must never raise
            pass
        self._clients.pop(name, None)

    def register_into(self, registry: ToolRegistry) -> list[str]:
        """Register discovered tools in the registry.

        Tool names are exposed unchanged unless that would collide with another
        tool; colliding names (across servers or against local tools) get a
        ``mcp__<server>__<tool>`` prefix. Returns the list of exposed names.
        """
        occurrences: Counter[str] = Counter()
        for specs in self._tool_specs.values():
            for spec in specs:
                occurrences[spec.name] += 1

        exposed_names: list[str] = []
        for server_name, specs in self._tool_specs.items():
            server_exposed: list[str] = []
            for spec in specs:
                if occurrences[spec.name] == 1 and spec.name not in registry:
                    exposed = spec.name
                else:
                    exposed = f"mcp__{_PREFIX_SAFE.sub('_', server_name)}__{spec.name}"
                if exposed in registry or exposed in self._routing:
                    # Still colliding after prefixing; impossible in practice.
                    continue
                self._routing[exposed] = (server_name, spec.name)
                self._exposed_specs[exposed] = spec
                try:
                    registry.register(
                        McpTool(
                            replace(spec, name=exposed),
                            self,
                            server_name,
                            spec.name,
                        )
                    )
                except ValueError:
                    del self._routing[exposed]
                    self._exposed_specs.pop(exposed, None)
                    continue
                server_exposed.append(exposed)
                exposed_names.append(exposed)
            self._exposed[server_name] = server_exposed
        return exposed_names

    async def call_tool(self, exposed_name: str, arguments: Mapping[str, Any]) -> str:
        """Execute one MCP tool call and normalize the result for the LLM."""
        route = self._routing.get(exposed_name)
        if route is None:
            return json_error(f"未知的 MCP 工具: {exposed_name}")
        server_name, tool_name = route
        client = self._clients.get(server_name)
        if client is None:
            return json_error(f"MCP Server '{server_name}' 未连接")

        try:
            result = await asyncio.wait_for(
                client.call_tool(tool_name, dict(arguments or {})),
                self._request_timeout,
            )
        except TimeoutError:
            return json_error(
                f"MCP 工具调用超时（{self._request_timeout:.0f} 秒）: {exposed_name}"
            )
        except Exception as exc:  # noqa: BLE001 - every failure becomes model data
            return json_error(f"MCP 工具调用失败: {_describe_exception(exc)}")
        return _format_tool_result(result)

    async def aclose(self) -> None:
        for name, client in list(self._clients.items()):
            try:
                await client.__aexit__(None, None, None)
            except Exception:  # noqa: BLE001
                pass
            self._clients.pop(name, None)
        self._tool_specs.clear()
        self._routing.clear()
        self._exposed.clear()
        self._exposed_specs.clear()


def _format_tool_result(result: CallToolResult) -> str:
    """Render text content, structured data and error flags as one string."""

    texts: list[str] = []
    for item in result.content:
        if isinstance(item, TextContent):
            texts.append(item.text)
        elif isinstance(item, ImageContent):
            texts.append(f"[图片内容: mime={item.mime_type}]")
        elif isinstance(item, EmbeddedResource):
            texts.append(f"[嵌入资源: {item.resource.uri}]")

    text = "\n".join(part for part in texts if part).strip()

    if result.is_error:
        detail = text or "工具返回了错误，但未提供详细信息"
        return json_error(detail)

    structured = result.structured_content
    if structured is not None:
        structured_text = json.dumps(structured, ensure_ascii=False, default=str)
        if text and text != structured_text:
            return f"{text}\n\nstructured_content:\n{structured_text}"
        return structured_text

    return text or "（工具执行成功，无返回内容）"
