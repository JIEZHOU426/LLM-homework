"""Agent Skills discovery and on-demand loading.

Discovery only parses the YAML frontmatter of each ``SKILL.md``; the full body
is read when the model explicitly calls the ``loadSkill`` tool. Skill metadata
is kept out of the conversation context until then.
"""

from __future__ import annotations

import json
import locale
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml

SKILL_FILE_NAME = "SKILL.md"
SKILLS_DIRECTORY = Path(".agents") / "skills"
DEFAULT_MAX_TEXT_BYTES = 2 * 1024 * 1024
SKILL_NAME_MAX_LENGTH = 64
SKILL_DESCRIPTION_MAX_LENGTH = 1024
_NON_NAME_CHARACTERS = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True, slots=True)
class Skill:
    """A discovered skill and the directory that contains it."""

    name: str
    description: str
    directory: Path
    skill_file: Path


class SkillCatalog:
    """Discovers skills under ``<project_root>/.agents/skills``."""

    def __init__(
        self,
        project_root: Path,
        skills: Iterable[Skill] = (),
        max_text_bytes: int = DEFAULT_MAX_TEXT_BYTES,
    ) -> None:
        self._project_root = Path(project_root).expanduser().resolve()
        self._skills = {skill.name: skill for skill in skills}
        self._max_text_bytes = max_text_bytes

    @property
    def project_root(self) -> Path:
        return self._project_root

    @property
    def skills(self) -> tuple[Skill, ...]:
        return tuple(self._skills.values())

    def __bool__(self) -> bool:
        return bool(self._skills)

    @classmethod
    def discover(
        cls,
        project_root: Path,
        max_text_bytes: int = DEFAULT_MAX_TEXT_BYTES,
    ) -> "SkillCatalog":
        root = Path(project_root).expanduser().resolve()
        skills_dir = root / SKILLS_DIRECTORY
        discovered: list[Skill] = []
        seen: set[str] = set()

        if skills_dir.is_dir():
            for child in sorted(
                skills_dir.iterdir(),
                key=lambda path: path.name.lower(),
            ):
                if not child.is_dir():
                    continue
                skill_file = child / SKILL_FILE_NAME
                if not skill_file.is_file():
                    continue
                metadata = _read_frontmatter(skill_file)
                if metadata is None:
                    continue
                name, description = metadata
                if name in seen:
                    continue
                seen.add(name)
                discovered.append(
                    Skill(
                        name=name,
                        description=description,
                        directory=child.resolve(),
                        skill_file=skill_file.resolve(),
                    )
                )

        return cls(root, discovered, max_text_bytes)

    def system_prompt(self) -> str:
        """Return the system-prompt section advertising available skills."""

        if not self._skills:
            return ""

        lines = ["You have access to the following skills:"]
        for skill in sorted(
            self._skills.values(),
            key=lambda item: item.name.lower(),
        ):
            lines.append(f"- '{skill.name}': {skill.description}")
        lines.append("")
        lines.append(
            "Use the 'loadSkill' tool to load the full instructions of a skill "
            "when needed. You can also load additional files referenced by a "
            "skill."
        )
        return "\n".join(lines)

    def load(self, name: Any, filename: Any = None) -> str:
        """Load a skill's ``SKILL.md`` or an attachment inside its directory."""

        if not isinstance(name, str) or not name.strip():
            return _error("参数 name 必须是非空字符串")

        skill = self._skills.get(name.strip())
        if skill is None:
            available = ", ".join(
                sorted(self._skills, key=str.lower)
            ) or "（无）"
            return _error(
                f"未找到技能: {name.strip()}。可用技能: {available}"
            )

        if filename is None:
            return self._load_skill_file(skill)

        if not isinstance(filename, str) or not filename.strip():
            return _error("参数 filename 必须是非空字符串")
        return self._load_attachment(skill, filename.strip())

    def create(self, name: Any, skill_context: Any) -> str:
        """Create a new skill directory and a spec-compliant ``SKILL.md``."""

        try:
            skill_name = _normalize_skill_name(name)
        except ValueError as exc:
            return _error(str(exc))

        if not isinstance(skill_context, str) or not skill_context.strip():
            return _error("参数 skillContext 必须是非空字符串")

        existing = self._find_existing(skill_name)
        if existing is not None:
            return _error(
                f"Skill 已存在: {skill_name}（{existing}），已拒绝覆盖。"
            )

        try:
            body, metadata = _parse_skill_context(skill_context)
            if not body.strip():
                raise ValueError("skillContext 必须包含正文内容")
            raw_description = metadata.get("description")
            if isinstance(raw_description, str) and raw_description.strip():
                description = _normalize_description(raw_description)
            else:
                description = _derive_description(body)
        except ValueError as exc:
            return _error(str(exc))

        target_dir = self._project_root / SKILLS_DIRECTORY / skill_name
        skill_file = target_dir / SKILL_FILE_NAME
        frontmatter = _build_frontmatter(skill_name, description, metadata)
        content = _render_skill_file(frontmatter, body)

        try:
            target_dir.parent.mkdir(parents=True, exist_ok=True)
            target_dir.mkdir(exist_ok=False)
        except FileExistsError:
            return _error(
                f"Skill 目录已存在: {target_dir}，已拒绝覆盖。"
            )
        except OSError as exc:
            return _error(f"创建 Skill 目录失败: {exc}")

        try:
            with skill_file.open("x", encoding="utf-8", newline="\n") as file:
                file.write(content)
        except FileExistsError:
            return _error(
                f"Skill 文件已存在: {skill_file}，已拒绝覆盖。"
            )
        except OSError as exc:
            try:
                target_dir.rmdir()
            except OSError:
                pass
            return _error(f"写入 SKILL.md 失败: {exc}")

        skill = Skill(
            name=skill_name,
            description=description,
            directory=target_dir.resolve(),
            skill_file=skill_file.resolve(),
        )
        self._skills[skill_name] = skill
        return _ok(
            name=skill_name,
            description=description,
            directory=str(skill.directory),
            path=str(skill.skill_file),
            message=(
                "Skill 创建成功。如需添加 references/、scripts/ 等目录或"
                "其他辅助文件，请继续调用文件工具。"
            ),
        )

    def _find_existing(self, skill_name: str) -> str | None:
        for existing_name, skill in self._skills.items():
            try:
                normalized = _normalize_skill_name(existing_name)
            except ValueError:
                continue
            if normalized == skill_name:
                return str(skill.directory)

        skills_dir = self._project_root / SKILLS_DIRECTORY
        if not skills_dir.is_dir():
            return None
        for child in skills_dir.iterdir():
            if not child.is_dir():
                continue
            try:
                normalized = _normalize_skill_name(child.name)
            except ValueError:
                continue
            if normalized == skill_name:
                return str(child)
        return None

    def _load_skill_file(self, skill: Skill) -> str:
        try:
            content = _read_text(skill.skill_file, self._max_text_bytes)
        except (OSError, ValueError) as exc:
            return _error(str(exc))
        return _ok(
            skill=skill.name,
            path=str(skill.skill_file),
            content=content,
        )

    def _load_attachment(self, skill: Skill, filename: str) -> str:
        raw_path = Path(filename).expanduser()

        exact_candidates: list[Path] = []
        if raw_path.is_absolute():
            exact_candidates.append(raw_path)
        else:
            exact_candidates.append(skill.directory / raw_path)
            exact_candidates.append(self._project_root / raw_path)

        seen: set[Path] = set()
        out_of_scope = False
        for candidate in exact_candidates:
            try:
                resolved = candidate.resolve()
            except OSError:
                continue
            if resolved in seen:
                continue
            seen.add(resolved)
            if not resolved.is_file():
                continue
            if not _is_within(resolved, skill.directory):
                out_of_scope = True
                continue
            return self._read_attachment(skill, resolved)

        if _is_bare_filename(filename):
            matches: list[Path] = []
            for path in skill.directory.rglob("*"):
                try:
                    if not path.is_file() or path.name != filename:
                        continue
                    resolved = path.resolve()
                except OSError:
                    continue
                if not _is_within(resolved, skill.directory):
                    continue
                if resolved not in matches:
                    matches.append(resolved)

            if len(matches) == 1:
                return self._read_attachment(skill, matches[0])
            if len(matches) > 1:
                return _ok(
                    skill=skill.name,
                    filename=filename,
                    candidates=[str(path) for path in sorted(matches)],
                    message=(
                        "找到多个同名文件，请从 candidates 中选择一个路径，"
                        "并将其作为 filename 再次调用 loadSkill。"
                    ),
                )

        if out_of_scope:
            return _error(
                f"文件不在技能目录内，已拒绝读取: {filename}"
            )
        return _error(f"未找到文件: {filename}")

    def _read_attachment(self, skill: Skill, path: Path) -> str:
        try:
            content = _read_text(path, self._max_text_bytes)
        except (OSError, ValueError) as exc:
            return _error(str(exc))
        return _ok(
            skill=skill.name,
            path=str(path),
            content=content,
        )


def _normalize_skill_name(raw: Any) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("参数 name 必须是非空字符串")

    name = _NON_NAME_CHARACTERS.sub("-", raw.strip().lower()).strip("-")
    if not name:
        raise ValueError(
            "Skill 名称必须包含英文字母或数字，例如 pdf-tools"
        )
    if len(name) > SKILL_NAME_MAX_LENGTH:
        raise ValueError(
            f"Skill 名称过长（{len(name)} 字符），"
            f"最多 {SKILL_NAME_MAX_LENGTH} 个字符"
        )
    return name


def _parse_skill_context(raw: str) -> tuple[str, dict[str, Any]]:
    """Split optional YAML frontmatter from the body supplied by the model."""

    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    if text.startswith("\ufeff"):
        text = text[1:]
    lines = text.split("\n")
    if lines[0].strip() != "---":
        return text.strip(), {}

    closing_index = next(
        (index for index in range(1, len(lines)) if lines[index].strip() == "---"),
        None,
    )
    if closing_index is None:
        raise ValueError("skillContext 的 YAML Frontmatter 缺少结束标记 ---")

    frontmatter = "\n".join(lines[1:closing_index])
    body = "\n".join(lines[closing_index + 1:]).strip("\n")

    try:
        metadata = yaml.safe_load(frontmatter) if frontmatter.strip() else {}
    except yaml.YAMLError as exc:
        raise ValueError(
            f"skillContext 的 YAML Frontmatter 无法解析: {exc}"
        ) from exc
    if not isinstance(metadata, dict):
        raise ValueError("skillContext 的 YAML Frontmatter 必须是键值对")
    return body, metadata


def _normalize_description(description: str) -> str:
    cleaned = " ".join(description.split())
    if not cleaned:
        raise ValueError("Skill description 不能为空")
    return cleaned[:SKILL_DESCRIPTION_MAX_LENGTH]


def _derive_description(body: str) -> str:
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = re.sub(r"^#{1,6}\s*", "", line)
        line = re.sub(r"^(?:[-*+]\s+|\d+\.\s+)", "", line)
        cleaned = " ".join(line.split())
        if cleaned:
            return cleaned[:SKILL_DESCRIPTION_MAX_LENGTH]
    raise ValueError("skillContext 缺少正文内容，无法生成 description")


def _build_frontmatter(
    name: str,
    description: str,
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    frontmatter: dict[str, Any] = {
        "name": name,
        "description": description,
    }
    for key, value in metadata.items():
        if key not in frontmatter:
            frontmatter[key] = value
    return frontmatter


def _render_skill_file(frontmatter: Mapping[str, Any], body: str) -> str:
    dumped = yaml.safe_dump(
        dict(frontmatter),
        allow_unicode=True,
        sort_keys=False,
        width=4096,
    ).strip()
    return f"---\n{dumped}\n---\n\n{body.strip()}\n"


def _read_frontmatter(path: Path) -> tuple[str, str] | None:
    """Read only the leading YAML frontmatter, never the skill body."""

    try:
        with path.open("r", encoding="utf-8-sig") as file:
            if file.readline().strip() != "---":
                return None
            lines: list[str] = []
            for line in file:
                if line.strip() == "---":
                    break
                lines.append(line)
            else:
                return None
    except (OSError, UnicodeDecodeError):
        return None

    try:
        metadata = yaml.safe_load("".join(lines))
    except yaml.YAMLError:
        return None
    if not isinstance(metadata, dict):
        return None

    name = metadata.get("name")
    description = metadata.get("description")
    if not isinstance(name, str) or not name.strip():
        return None
    if not isinstance(description, str) or not description.strip():
        return None
    return name.strip(), " ".join(description.split())


def _is_bare_filename(raw: str) -> bool:
    path = Path(raw)
    return not path.is_absolute() and len(path.parts) == 1


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _read_text(path: Path, max_text_bytes: int) -> str:
    size = path.stat().st_size
    if size > max_text_bytes:
        raise ValueError(
            f"文件过大（{size} 字节），超过读取上限 {max_text_bytes} 字节"
        )

    data = path.read_bytes()
    if b"\x00" in data:
        raise ValueError("仅支持纯文本文件：检测到二进制内容")

    for encoding in ("utf-8-sig", locale.getpreferredencoding(False), "gbk"):
        try:
            return data.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    raise ValueError("仅支持纯文本文件：无法识别文本编码")


def _error(message: str) -> str:
    return json.dumps({"error": message}, ensure_ascii=False)


def _ok(**payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False)
