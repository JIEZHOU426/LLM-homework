"""The ``loadSkill`` tool backed by a :class:`SkillCatalog`."""

from __future__ import annotations

from typing import Any, Mapping

from ..skills import SkillCatalog
from .base import FunctionTool, Tool, ToolSpec


def build_skill_tool(catalog: SkillCatalog) -> Tool:
    def _load_skill(arguments: Mapping[str, Any]) -> str:
        return catalog.load(
            arguments.get("name"),
            arguments.get("filename"),
        )

    return FunctionTool(
        ToolSpec(
            name="loadSkill",
            description=(
                "按需加载 Skill 的完整说明或附件文件。仅提供 name 时读取该 "
                "Skill 的 SKILL.md 全文；同时提供 filename 时读取该 Skill "
                "目录内的附件，不重复加载 SKILL.md。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Skill 名称，来自系统提示中的技能列表",
                    },
                    "filename": {
                        "type": "string",
                        "description": (
                            "可选：要加载的附件文件。支持相对 Skill 目录的"
                            "路径、项目根目录相对路径或绝对路径；仅提供文件名"
                            "时会递归搜索该 Skill 目录。"
                        ),
                    },
                },
                "required": ["name"],
            },
        ),
        _load_skill,
    )
