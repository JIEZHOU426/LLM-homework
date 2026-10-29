import configparser
import json
import locale
import mimetypes
import os
import shutil
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

config = configparser.ConfigParser()
config.read(BASE_DIR / "config.ini", encoding="utf-8")

api_key = os.getenv("DEEPSEEK_API_KEY") or config.get("LLM", "api_key", fallback="")
if not api_key or api_key.startswith("sk-your"):
    raise SystemExit(
        "未配置 API Key：请在 .env 中设置 DEEPSEEK_API_KEY，"
        "或在 config.ini 中填写 api_key"
    )

client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com/v1")

MAX_TEXT_BYTES = 2 * 1024 * 1024

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "getDate",
            "description": "获取当前电脑的日期和时间，可用于回答今天是星期几、现在几点",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "isleapyear",
            "description": "判断输入的年份是否为闰年",
            "parameters": {
                "type": "object",
                "properties": {
                    "year": {
                        "type": "integer",
                        "description": "要判断的年份，例如 2024",
                    }
                },
                "required": ["year"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_cwd",
            "description": "获取当前工作目录的绝对路径",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "列出指定目录下所有文件和子目录",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "目录路径，默认为当前工作目录",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_file_type",
            "description": "获取指定文件的文件类型（MIME 类型、扩展名、文本/二进制）",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "文件路径",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_text_file",
            "description": "读取指定纯文本文件的内容，非纯文本文件会返回错误",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "文件路径",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_file",
            "description": "根据指定的目录和文件名创建新文件，目录不存在时会自动创建",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "文件所在目录",
                    },
                    "filename": {
                        "type": "string",
                        "description": "文件名，例如 notes.txt",
                    },
                    "content": {
                        "type": "string",
                        "description": "初始文本内容，默认为空",
                    },
                },
                "required": ["directory", "filename"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "编辑指定纯文本文件的内容，支持覆盖或追加",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "文件路径",
                    },
                    "content": {
                        "type": "string",
                        "description": "要写入的文本内容",
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["overwrite", "append"],
                        "description": "编辑方式：overwrite 覆盖，append 追加，默认 overwrite",
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_directory",
            "description": "创建新目录，父目录不存在时会自动创建",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要创建的目录路径",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_directory",
            "description": "删除指定目录，非空目录会连同其中所有内容一起删除",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要删除的目录路径",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_file",
            "description": "删除指定文件",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要删除的文件路径",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rename_path",
            "description": "重命名文件或目录，也可移动到新位置",
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {
                        "type": "string",
                        "description": "原文件或目录路径",
                    },
                    "target": {
                        "type": "string",
                        "description": "新的文件或目录路径",
                    },
                },
                "required": ["source", "target"],
            },
        },
    },
]


def resolve_path(raw: str) -> Path:
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("路径不能为空")
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve()


def detect_encoding(data: bytes) -> str | None:
    for encoding in ("utf-8", locale.getpreferredencoding(False), "gbk"):
        try:
            data.decode(encoding)
            return encoding
        except (UnicodeDecodeError, LookupError):
            continue
    return None


def is_text_data(data: bytes) -> bool:
    if b"\x00" in data:
        return False
    return detect_encoding(data) is not None


def json_error(message: str) -> str:
    return json.dumps({"error": message}, ensure_ascii=False)


def get_date() -> str:
    if sys.platform == "win32":
        command = "date /t & time /t"
    else:
        command = "date"
    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        encoding=locale.getpreferredencoding(False),
        errors="replace",
    )
    output = (result.stdout or "").strip()
    if result.returncode != 0:
        error = (result.stderr or "").strip()
        return json_error(error or "date command failed")
    return json.dumps({"datetime": output}, ensure_ascii=False)


def is_leap_year(year: int) -> bool:
    if year % 400 == 0:
        return True
    if year % 100 == 0:
        return False
    return year % 4 == 0


def isleapyear(arguments: str) -> str:
    try:
        args = json.loads(arguments or "{}")
        year = int(args["year"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        return json_error(f"参数错误: {exc}")
    return json.dumps(
        {"year": year, "isLeapYear": is_leap_year(year)},
        ensure_ascii=False,
    )


def get_cwd() -> str:
    return json.dumps({"cwd": str(Path.cwd())}, ensure_ascii=False)


def list_directory(raw_path: str = ".") -> str:
    path = resolve_path(raw_path)
    if not path.exists():
        return json_error(f"目录不存在: {path}")
    if not path.is_dir():
        return json_error(f"不是目录: {path}")

    entries = []
    for child in sorted(
        path.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower())
    ):
        if child.is_symlink():
            kind = "symlink"
        elif child.is_dir():
            kind = "directory"
        elif child.is_file():
            kind = "file"
        else:
            kind = "other"
        entry = {
            "name": child.name,
            "path": str(child),
            "type": kind,
        }
        if kind == "file":
            try:
                entry["size"] = child.stat().st_size
            except OSError:
                entry["size"] = None
        entries.append(entry)

    return json.dumps(
        {"path": str(path), "count": len(entries), "entries": entries},
        ensure_ascii=False,
    )


def get_file_type(raw_path: str) -> str:
    path = resolve_path(raw_path)
    if not path.exists():
        return json_error(f"路径不存在: {path}")

    if path.is_symlink():
        kind = "symlink"
    elif path.is_dir():
        kind = "directory"
    elif path.is_file():
        kind = "file"
    else:
        kind = "other"

    result = {
        "path": str(path),
        "kind": kind,
        "extension": path.suffix,
    }

    if kind != "file":
        return json.dumps(result, ensure_ascii=False)

    mime_type, mime_encoding = mimetypes.guess_type(path.name)
    with path.open("rb") as file:
        head = file.read(8192)
    result.update(
        {
            "mimeType": mime_type or "application/octet-stream",
            "mimeEncoding": mime_encoding,
            "isText": is_text_data(head),
            "size": path.stat().st_size,
        }
    )
    return json.dumps(result, ensure_ascii=False)


def read_file_content(path: Path) -> tuple[str, str]:
    size = path.stat().st_size
    if size > MAX_TEXT_BYTES:
        raise ValueError(f"文件过大（{size} 字节），超过读取上限 {MAX_TEXT_BYTES} 字节")
    data = path.read_bytes()
    if b"\x00" in data:
        raise ValueError("仅支持纯文本文件：检测到二进制内容")
    encoding = detect_encoding(data)
    if encoding is None:
        raise ValueError("仅支持纯文本文件：无法识别文本编码")
    return data.decode(encoding), encoding


def read_text_file(raw_path: str) -> str:
    path = resolve_path(raw_path)
    if not path.exists():
        return json_error(f"文件不存在: {path}")
    if not path.is_file():
        return json_error(f"不是文件: {path}")
    try:
        content, encoding = read_file_content(path)
    except (OSError, ValueError) as exc:
        return json_error(str(exc))
    return json.dumps(
        {
            "path": str(path),
            "encoding": encoding,
            "size": path.stat().st_size,
            "content": content,
        },
        ensure_ascii=False,
    )


def create_file(directory: str, filename: str, content: str = "") -> str:
    if not filename or Path(filename).name != filename:
        return json_error("filename 必须是文件名，不能包含路径分隔符")
    directory_path = resolve_path(directory)
    if directory_path.exists() and not directory_path.is_dir():
        return json_error(f"不是目录: {directory_path}")
    directory_path.mkdir(parents=True, exist_ok=True)

    file_path = (directory_path / filename).resolve()
    if file_path.exists():
        return json_error(f"文件已存在: {file_path}")

    file_path.write_text(content or "", encoding="utf-8")
    return json.dumps(
        {
            "path": str(file_path),
            "directory": str(directory_path),
            "size": file_path.stat().st_size,
        },
        ensure_ascii=False,
    )


def edit_file(raw_path: str, content: str, mode: str = "overwrite") -> str:
    path = resolve_path(raw_path)
    if not path.exists():
        return json_error(f"文件不存在: {path}")
    if not path.is_file():
        return json_error(f"不是文件: {path}")
    if mode not in ("overwrite", "append"):
        return json_error("mode 只支持 overwrite 或 append")
    if not isinstance(content, str):
        return json_error("content 必须是字符串")

    try:
        _, encoding = read_file_content(path)
    except (OSError, ValueError) as exc:
        return json_error(str(exc))

    if mode == "overwrite":
        path.write_text(content, encoding=encoding)
    else:
        with path.open("a", encoding=encoding, newline="") as file:
            file.write(content)

    return json.dumps(
        {
            "path": str(path),
            "mode": mode,
            "encoding": encoding,
            "size": path.stat().st_size,
        },
        ensure_ascii=False,
    )


def create_directory(raw_path: str) -> str:
    path = resolve_path(raw_path)
    if path.exists():
        if path.is_dir():
            return json_error(f"目录已存在: {path}")
        return json_error(f"路径已存在且不是目录: {path}")
    path.mkdir(parents=True, exist_ok=False)
    return json.dumps({"path": str(path), "created": True}, ensure_ascii=False)


def ensure_safe_delete(path: Path) -> None:
    resolved = path.resolve()
    cwd = Path.cwd().resolve()
    forbidden = {Path(resolved.anchor).resolve(), Path.home().resolve(), cwd}
    if resolved in forbidden or resolved in cwd.parents:
        raise ValueError(f"出于安全考虑，不允许删除该目录: {resolved}")


def delete_directory(raw_path: str) -> str:
    path = resolve_path(raw_path)
    if not path.exists():
        return json_error(f"目录不存在: {path}")
    if not path.is_dir() or path.is_symlink():
        return json_error(f"不是目录: {path}")
    try:
        ensure_safe_delete(path)
    except ValueError as exc:
        return json_error(str(exc))

    shutil.rmtree(path)
    return json.dumps({"path": str(path), "deleted": True}, ensure_ascii=False)


def delete_file(raw_path: str) -> str:
    path = resolve_path(raw_path)
    if not path.exists() and not path.is_symlink():
        return json_error(f"文件不存在: {path}")
    if path.is_dir() and not path.is_symlink():
        return json_error(f"是目录而不是文件，请使用 delete_directory: {path}")
    try:
        path.unlink()
    except OSError as exc:
        return json_error(str(exc))
    return json.dumps({"path": str(path), "deleted": True}, ensure_ascii=False)


def rename_path(source: str, target: str) -> str:
    source_path = resolve_path(source)
    target_path = resolve_path(target)
    if not source_path.exists() and not source_path.is_symlink():
        return json_error(f"源路径不存在: {source_path}")
    if target_path.exists() or target_path.is_symlink():
        return json_error(f"目标路径已存在: {target_path}")
    try:
        shutil.move(str(source_path), str(target_path))
    except OSError as exc:
        return json_error(str(exc))
    return json.dumps(
        {
            "source": str(source_path),
            "target": str(target_path),
            "renamed": True,
        },
        ensure_ascii=False,
    )


def run_tool(name: str, arguments: str) -> str:
    try:
        args = json.loads(arguments or "{}")
        if not isinstance(args, dict):
            return json_error("工具参数必须是 JSON 对象")
    except json.JSONDecodeError as exc:
        return json_error(f"参数解析失败: {exc}")

    try:
        if name == "getDate":
            return get_date()
        if name == "isleapyear":
            return isleapyear(arguments)
        if name == "get_cwd":
            return get_cwd()
        if name == "list_directory":
            return list_directory(args.get("path", "."))
        if name == "get_file_type":
            return get_file_type(args["path"])
        if name == "read_text_file":
            return read_text_file(args["path"])
        if name == "create_file":
            return create_file(
                args["directory"], args["filename"], args.get("content", "")
            )
        if name == "edit_file":
            return edit_file(
                args["path"], args["content"], args.get("mode", "overwrite")
            )
        if name == "create_directory":
            return create_directory(args["path"])
        if name == "delete_directory":
            return delete_directory(args["path"])
        if name == "delete_file":
            return delete_file(args["path"])
        if name == "rename_path":
            return rename_path(args["source"], args["target"])
    except KeyError as exc:
        return json_error(f"缺少参数: {exc}")
    except (OSError, TypeError, ValueError) as exc:
        return json_error(str(exc))
    return json_error(f"unknown tool: {name}")


def answer(messages: list) -> None:
    while True:
        stream = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            tools=TOOLS,
            stream=True,
        )

        content_parts = []
        tool_calls = {}
        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta

            if delta.content:
                content_parts.append(delta.content)
                print(delta.content, end="", flush=True)

            if delta.tool_calls:
                for tool_call in delta.tool_calls:
                    entry = tool_calls.setdefault(
                        tool_call.index,
                        {
                            "id": "",
                            "type": "function",
                            "function": {"name": "", "arguments": ""},
                        },
                    )
                    if tool_call.id:
                        entry["id"] = tool_call.id
                    if tool_call.type:
                        entry["type"] = tool_call.type
                    if tool_call.function:
                        if tool_call.function.name:
                            entry["function"]["name"] += tool_call.function.name
                        if tool_call.function.arguments:
                            entry["function"]["arguments"] += (
                                tool_call.function.arguments
                            )
        if content_parts:
            print()

        content = "".join(content_parts)

        if not tool_calls:
            messages.append({"role": "assistant", "content": content})
            return

        calls = [tool_calls[index] for index in sorted(tool_calls)]
        messages.append(
            {
                "role": "assistant",
                "content": content,
                "tool_calls": calls,
            }
        )
        for call in calls:
            result = run_tool(call["function"]["name"], call["function"]["arguments"])
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": result,
                }
            )


def main() -> None:
    messages = []
    print("输入问题回车开始对话，按 Ctrl+C 退出。")

    try:
        while True:
            try:
                question = input("请输入问题: ")
            except EOFError:
                break
            if not question.strip():
                continue

            print("---")
            messages.append({"role": "user", "content": question})
            answer(messages)
            print("---")
    except KeyboardInterrupt:
        print("\n已退出。")


if __name__ == "__main__":
    main()
