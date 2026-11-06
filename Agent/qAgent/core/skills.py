"""Agent Skills discovery and on-demand loading.

Discovery only parses the YAML frontmatter of each ``SKILL.md``; the full body
is read when the model explicitly calls the ``loadSkill`` tool. Skill metadata
is kept out of the conversation context until then.
"""

from __future__ import annotations

import json
import locale
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml

SKILL_FILE_NAME = "SKILL.md"
SKILLS_DIRECTORY = Path(".agents") / "skills"
DEFAULT_MAX_TEXT_BYTES = 2 * 1024 * 1024


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
