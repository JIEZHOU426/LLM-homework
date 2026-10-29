import configparser
import json
import locale
import os
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

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "getDate",
            "description": "获取当前电脑的日期和时间",
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
]


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
        return json.dumps(
            {"error": error or "date command failed"}, ensure_ascii=False
        )
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
        return json.dumps({"error": f"参数错误: {exc}"}, ensure_ascii=False)
    return json.dumps(
        {"year": year, "isLeapYear": is_leap_year(year)},
        ensure_ascii=False,
    )


def run_tool(name: str, arguments: str) -> str:
    if name == "getDate":
        return get_date()
    if name == "isleapyear":
        return isleapyear(arguments)
    return json.dumps({"error": f"unknown tool: {name}"}, ensure_ascii=False)


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
