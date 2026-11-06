"""The ``loadSkill`` / ``createSkill`` tools backed by a :class:`SkillCatalog`."""

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


def build_create_skill_tool(catalog: SkillCatalog) -> Tool:
    def _create_skill(arguments: Mapping[str, Any]) -> str:
        return catalog.create(
            arguments.get("name"),
            arguments.get("skillContext"),
        )

    return FunctionTool(
        ToolSpec(
            name="createSkill",
            description=(
                "根据用户的自然语言要求创建新的 Agent Skill。工具会在项目根"
                "目录的 .agents/skills/ 下创建与小写字母、数字和连字符组成的"
                "名称对应的子目录，并生成符合 Agent Skills 规范的 SKILL.md。"
                "若目标 Skill 已存在则返回错误，不会覆盖原内容。如需添加 "
                "references/、scripts/ 等目录或辅助文件，请随后调用文件工具。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": (
                            "Skill 名称，会自动规范为小写字母、数字和连字符"
                            "组成的格式，例如 pdf-tools"
                        ),
                    },
                    "skillContext": {
                        "type": "string",
                        "description": (
                            "要写入 SKILL.md 的完整内容。可包含 YAML "
                            "Frontmatter（建议在其中提供 description），也可"
                            "只提供正文；工具会自动补全规范要求的 name 和 "
                            "description。"
                        ),
                    },
                },
                "required": ["name", "skillContext"],
            },
        ),
        _create_skill,
    )
