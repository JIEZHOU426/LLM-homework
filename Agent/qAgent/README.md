# qAgent

基于 `Agent/Project2/chat_file.py` 改造的 DeepSeek Agent。业务逻辑与界面完全分离：
`core` 不依赖任何 UI，`tui` 只是其中一个前端实现。后续可以新增 `web`、`desktop`
等目录，复用同一套核心能力。

## 目录结构

```text
qAgent/
├── main.py                  # TUI 启动入口（含 config.ini 引导）
├── AGENT.md                 # 项目规则示例（启动时一次性注入会话）
├── requirements.txt
├── .env.example
├── config.ini.example
├── tests/                   # unittest 自测（无需网络与真实 Key）
│   ├── test_clock.py        # 闰年规则边界 + 真实日期输出
│   ├── test_filesystem.py   # 10 类文件语义 + 参数错误 + 路径边界
│   ├── test_skills.py       # 技能创建 / 拒绝覆盖 / 发现 / 加载
│   ├── test_sessions.py     # 会话保存 → 列表 → 恢复
│   ├── test_call_log.py     # 工具调用日志（含错误码、参数脱敏）
│   ├── test_agents_md.py    # 规则文件命名与等价名回退
│   └── test_turn_guard.py   # 单轮工具步数上限真实中止循环
├── core/                    # 业务核心（禁止导入 tui / web / desktop）
│   ├── config.py            # Settings：读取 .env 与 config.ini（含全部默认值）
│   ├── events.py            # 核心向前端输出的事件协议
│   ├── agent.py             # ChatAgent：对话状态 + 流式 + 工具调用循环
│   ├── agents_md.py         # AGENT.md / AGENTS.md 读取与注入消息构造
│   ├── call_log.py          # 工具调用 JSONL 日志（耗时 + 错误码）
│   ├── sessions.py          # 会话事件日志：保存 / 列表 / 恢复
│   ├── compact.py           # Token 估算 / 上下文归档 / 摘要提示词
│   ├── skills.py            # Agent Skills 发现、元数据与按需加载
│   ├── llm/
│   │   └── client.py        # OpenAI 兼容客户端构造
│   └── tools/
│       ├── base.py          # Tool / ToolSpec / FunctionTool 契约
│       ├── registry.py      # 注册、Schema 导出、参数校验、分发与调用日志
│       ├── common.py        # 路径边界、编码、文本读取、删除保护
│       ├── clock.py         # getDate、isleapyear
│       ├── filesystem.py    # 10 个本地文件操作工具
│       ├── mcp_client.py    # MCP 客户端：连接、发现、路由与调用
│       ├── search.py        # searchWeb：百度千帆联网搜索
│       ├── skills.py        # loadSkill / createSkill
│       └── web.py           # fetchweb：网页正文抓取与 Markdown 转换
└── tui/                     # Textual 前端（只依赖 core 的公开接口）
    ├── app.py               # 组合根：把核心事件映射为界面行为
    ├── bootstrap.py         # config.ini 缺失时生成 mock 模板
    ├── screens.py           # 会话选择面板（含 r 重新扫描）/ 配置引导对话框
    ├── styles.tcss
    ├── __main__.py
    └── widgets/
        ├── chat.py          # ChatView / MessageCard
        ├── compact_panel.py # CompactPanel：压缩前后的双栏对照
        ├── header.py        # AppHeader：品牌、模型与实时状态
        ├── hints.py         # HintBar：常用快捷键
        ├── input.py         # ChatInput（斜杠补全键位）
        ├── popup.py         # CommandPopup：斜杠命令补全面板
        ├── sidebar.py       # McpSidebar：MCP 服务器与工具边栏
        └── status.py        # StatusBar：cwd / tools / skills
```

依赖方向严格单向：

```text
tui ──> core
web ──> core        （未来）
desktop ──> core    （未来）
core ──> 无 UI 依赖
```

## 分层职责

| 层 | 职责 | 不负责 |
| --- | --- | --- |
| `core.config` | 读取配置、校验 API Key | 打印错误、退出进程 |
| `core.tools` | 工具定义、Schema、参数校验、执行 | 如何展示工具结果 |
| `core.agent` | 对话历史、LLM 流式请求、工具调用循环 | 终端渲染、输入法、窗口 |
| `tui` | 布局、输入、流式渲染、快捷键 | 直接调用 OpenAI 或执行工具 |

## 核心事件协议

`ChatAgent.send(text)` 返回异步事件流，前端只需消费以下事件：

| 事件 | 含义 |
| --- | --- |
| `TextDelta` | 助手回复的一个增量片段 |
| `ToolCallRequested` | 模型请求调用工具 |
| `ToolCallCompleted` | 工具执行完成，`result` 为 JSON 字符串 |
| `TurnCompleted` | 一轮对话结束（包含所有工具往返） |
| `ContextWarning` | 上下文用量超过压缩阈值，暂停新提示词 |
| `CompactionStarted` / `CompactionCompleted` / `CompactionFailed` | `/compact` 压缩流程的状态 |
| `AgentError` | 可展示给用户的错误 |

`core` 不关心事件被渲染成文本、网页 SSE 还是 Qt 信号。

## 运行

```bash
cd Agent/qAgent
py -m pip install -r requirements.txt
py main.py
```

或者：

```bash
py -m tui
```

### 配置引导（config.ini）

qAgent 启动时会检查**当前工作目录**的 `config.ini`：

- 文件不存在时，自动创建一份完整的模板并填入 **mock 占位信息**
  （`tui/bootstrap.py`），同时在界面弹出对话框提示：填写配置后
  **重启 qAgent 才能正常工作**；
- 文件存在但 `[LLM] api_key` 仍是占位值（`sk-your-…`）时，界面提示
  未配置并禁用输入，直到填写真实 Key 后重启。

所有可调参数均从 `config.ini`（含 `.env` 环境变量覆盖）读取，未配置时使用
`core/config.py` 中的内置默认值。完整模板见 `config.ini.example`：

| 配置节 | 键 | 默认值 | 作用 |
| --- | --- | --- | --- |
| `[LLM]` | api_key / base_url / model / timeout / context_window | — | API Key、端点、模型、请求超时、上下文窗口 |
| `[files]` | max_text_bytes | 2 MB | 单文件读写上限 |
| `[files]` | confine_to_workspace | `true` | 文件工具路径边界（越界返回 `PATH_OUTSIDE_WORKSPACE`） |
| `[agent]` | max_steps | 12 | 单轮最多工具往返次数 |
| `[agent]` | turn_timeout | 600 秒 | 单轮总时限 |
| `[agents]` | filename | `AGENT.md` | 项目规则文件名（可用 `QAGENT_AGENTS_FILE` 覆盖） |
| `[log]` | enabled | `true` | 工具调用日志开关 |
| `[compact]` | threshold / summary_tokens | 0.6 / 5000 | 压缩阈值与摘要长度 |
| `[mcp]` | request_timeout / connect_timeout | 120 / 20 秒 | MCP 调用与连接超时 |
| `[ui]` | tool_result_max_chars | 4000 | 界面展示的工具结果截断长度 |
| `[search]` | baidu_api_key | 空 | 百度千帆联网搜索 Key |

使用联网搜索工具 `searchWeb` 还需要百度千帆 API Key（`[search]` 的
`baidu_api_key` 或 `.env` 中的 `BAIDU_SEARCH_API_KEY`）。未配置时程序
仍可启动，只有调用 `searchWeb` 时才会向模型返回缺少配置的错误提示。

## 会话管理与斜杠命令

所有会话以 JSONL 事件日志保存在 `<工作区>/.agents/sessions/<会话号>.jsonl`
（`meta` 头 + `agents_md` 事件 + 逐条 `message` 事件）。

输入 `/` 会弹出**命令补全面板**：`↑↓` 选择、`Tab`（或 `Enter`）补全、
`Esc` 关闭，输入持续过滤。

| 命令 | 说明 |
| --- | --- |
| `/help` | 显示命令帮助 |
| `/new` | 新建会话，当前会话**自动保存**到事件日志 |
| `/resume`、`/sessions` | 打开历史会话面板：`↑↓` 选择、`Enter` 恢复、`Esc` 取消、`r` 刷新 |
| `/save` | 保存当前会话 |
| `/clear` | 放弃当前对话内容并开启新会话（不保存） |
| `/compact [备注]` | 压缩上下文（原始对话先归档，再生成摘要替换） |
| `/mcp` | 显示 MCP 服务器与可用工具 |
| `/agents` | 查看项目规则文件（AGENT.md / AGENTS.md）注入状态 |
| `/context` | 查看上下文用量统计 |
| `/quit`、`/exit` | 退出（自动保存脏会话） |

快捷键：`Ctrl+Q` 退出（同样自动保存），`Ctrl+L` 清空对话。

## 项目规则文件支持（AGENT.md / AGENTS.md，一次注入，全程复用）

会话首次加载时，如果工作目录存在项目规则文件，其内容会：

1. 作为一条 `system` 消息追加到聊天历史的最前端（位于 Skills 系统提示词
   之后、第一条用户消息之前，最大化前缀缓存命中）；
2. 持久化到会话事件日志（`agents_md` 事件），`/save`、`/new`、`/quit`
   自动保存时一并写入；
3. 后续所有轮次直接复用同一条消息，不再重复读取；
4. `/compact` 压缩与 `/resume` 恢复会话时，从事件日志中取回原始内容并
   重新注入，保证提示词前缀稳定。

文件名规则：默认 `AGENT.md`，`AGENTS.md` 与之互为等价名（配置其中一个时，
找不到会回退到另一个）；自定义文件名通过 `[agents] filename` 或环境变量
`QAGENT_AGENTS_FILE` 指定，此时只探测该文件（避免"配了自定义却悄悄读到
AGENTS.md"）。文件超过 1 MB 时截断读取，缺失或不可读时静默跳过、不报错。
本仓库自带一个示例：[`AGENT.md`](./AGENT.md)。`/agents` 随时查看注入状态。

## MCP 服务器与边栏

TUI 右侧有专用**边栏**，展示当前已连接的 MCP 服务器及其所有可用工具。
MCP 为**异步加载**：程序先完成 TUI 界面渲染（边栏显示“加载中”），随后在
后台连接 `.mcp.json` 中的各服务器，连接完成后动态刷新边栏、状态栏工具
数量并在对话区追加连接报告。连接超时、调用超时等参数在 `[mcp]` 节配置。
使用 `/mcp` 可随时在对话区查看同样的快照。

MCP 服务器配置：

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "."]
    },
    "http-server": {
      "url": "https://example.com/mcp"
    }
  }
}
```

## 上下文压缩与用量监控

qAgent 能在有限上下文窗口内持续工作，全部由 `core` 实现，不依赖向量数据库
或 Embedding：

- **用量监控**：每次模型响应结束后统计上下文 tokens（System Prompt、
  User Prompt、对话历史与工具调用消息都计入）。优先读取 API 返回的
  `prompt_tokens` / `completion_tokens`（流式请求自动加
  `stream_options.include_usage`），拿不到时使用内置启发式估算
  （CJK 约 1 token/字，其余约 4 字符 1 token）。顶部栏中间醒目显示
  `上下文 used/limit (pct%)`，例如 `上下文 12.5k / 64k · 20%`；若无法从
  配置获取模型上下文窗口，将按 128k（131072）默认值处理并标注
  `（默认）`。
- **阈值告警与暂停**：配置 `[LLM] context_window`（不配置视为未知 →
  128k 默认）与 `[compact] threshold`（默认 0.6）。用量达到 60% 时发出
  `ContextWarning` 并暂停接受新的普通提示词，直到压缩成功结束；期间
  仍可执行 `/compact`。
- **`/compact` 手动压缩**：压缩期间 Agent 进入专用状态，只允许调用一次
  LLM 生成摘要（不传入任何工具；输出目标约 5,000 tokens，`max_tokens`
  由 `[compact] summary_tokens` 控制，默认 5000），归档与替换上下文由
  程序完成：

  1. 先把完整原始对话（角色、内容、工具调用参数、工具返回结果、顺序逐行
     保留）写入 `<工作区>/.agents/context/<YYYYMMDD-HHMMSS>.jsonl`；
     归档失败则取消压缩、上下文保持不变。
  2. 调用 LLM（无工具）使用 `core/compact.py` 中的上下文压缩专用
     Prompt 生成摘要：用户目标与要求、已完成的工作、当前工作状态、
     关键技术信息、关键决策与原因、下一步任务。
  3. 用 "系统提示词 + 摘要用户消息" 替换对话历史；工具定义保持不变。
     摘要末尾自动追加归档说明（压缩时间、归档编号、提示可用
     `recallContext` 检索），统计与暂停状态随即重置。压缩成功后解除
     输入限制，并弹出双栏结果面板：左侧为压缩前原始上下文，右侧为
     压缩摘要，支持独立滚动，点击 "关闭" 按钮（或 `Esc`）关闭。压缩
     失败时保留原上下文、报告错误，可重新执行 `/compact`。

  1. 归档示例：

  ```json
  {"type": "meta", "archived_at": "2026-10-22T15:30:00", "model": "deepseek-chat", ...}
  {"type": "message", "index": 0, "role": "system", "content": "..."}
  {"type": "message", "index": 1, "role": "user", "content": "..."}
  {"type": "message", "index": 2, "role": "assistant", "tool_calls": [...]  }
  {"type": "message", "index": 3, "role": "tool", "tool_call_id": "...", "content": "..."}
  ```

- **recallContext 工具**：注册为普通 Function Calling 工具，让模型在
  发现压缩摘要缺少历史细节时主动检索原始记录。参数 `text` 必填
  （支持空格分隔多个关键词，需同时命中），`id` 可选（指定归档编号，
  如 `20261022-153000`；省略时检索全部归档）。实现为 Python 本地
  全文关键词匹配（不使用向量数据库），返回命中片段、归档编号与所在
  位置；匹配过多时限制返回数量与总长度，避免检索结果再次占满上下文。

- **配置示例**（`config.ini`）：

  ```ini
  [LLM]
  ; 不配置时视为未知，按 128k 默认值处理并在 UI 标注（默认）
  ; context_window = 65536

  [compact]
  threshold = 0.6
  summary_tokens = 5000
  ```

## 工具

共 17 个（另有 MCP 服务器提供的工具动态并入）：

- 时间与日期：`getDate`、`isleapyear`
- 文件与目录：`get_cwd`、`list_directory`、`get_file_type`、`read_text_file`、
  `create_file`、`edit_file`、`create_directory`、`delete_directory`、
  `delete_file`、`rename_path`
- 网页内容：`fetchweb`
- 联网搜索：`searchWeb`
- 技能：`loadSkill`、`createSkill`
- 上下文归档检索：`recallContext`

### 工具执行护栏

`ChatAgent.send()` 有两个独立保护，避免模型陷入工具死循环：

| 护栏 | 配置 | 行为 |
| --- | --- | --- |
| 单轮步数上限 | `[agent] max_steps`（默认 12） | 超过即 `AgentError` 中止本轮，已执行的结果仍在历史里，下一轮可继续 |
| 单轮总时限 | `[agent] turn_timeout`（默认 600 秒） | 超时中止本轮并提示调整配置 |

### 路径边界

`[files] confine_to_workspace = true`（默认）时，10 个文件工具的每个路径参数
都会先做 `resolve()` 再判断是否落在工作目录内，越界返回
`{"error": "...PATH_OUTSIDE_WORKSPACE..."}`，可执行文件内容不受影响；需要
跨目录时显式改成 `false`。删除目录仍额外禁止磁盘根目录、用户主目录、当前
工作目录及其父目录。

### 工具调用日志

每次工具调用往 `<工作目录>/.agents/logs/tool-calls.jsonl` 追加一行：

```json
{"ts": "2026-11-12T15:30:00", "event": "tool_call", "name": "read_text_file",
 "ok": false, "code": "PATH_OUTSIDE_WORKSPACE", "dur_ms": 3, "args": ["path"]}
```

只记录**参数名**，不记录参数值（避免文件内容或密钥入库）；写日志失败只告警
一次，绝不影响对话。`[log] enabled = false` 可整体关闭。

## 自测

```bash
cd Agent/qAgent
py -m unittest discover -s tests -t . -v
```

36 个用例全部不依赖网络与真实 API Key（Agent 主循环用假客户端驱动），覆盖：
闰年规则边界、10 类文件语义与参数错误、路径边界（含相对路径逃逸）、技能
创建与拒绝覆盖、会话保存/列表/恢复往返、规则文件命名与等价名回退、调用日志
（含错误码与参数脱敏）、单轮步数上限真实中止循环。

## Agent Skills

qAgent 以**程序启动时的工作目录**作为项目根目录，扫描
`<项目根>/.agents/skills/` 下的各个 Skill 子目录。每个子目录至少包含一个
`SKILL.md`，文件开头使用 YAML Frontmatter 声明 `name` 和 `description`：

```markdown
---
name: pdf
description: 读取、拆分和合并 PDF 文件。
---

# PDF 技能

这里是完整说明，只有在模型调用 `loadSkill` 时才会进入上下文。
```

初始化时只读取 `name` 和 `description`，并把它们加入 System Prompt。模型需要
详细步骤时调用：

```text
loadSkill(name="pdf")
loadSkill(name="pdf", filename="scripts/merge.py")
```

`filename` 支持相对 Skill 目录、项目根目录相对路径和绝对路径；只给文件名时会
递归搜索该 Skill 目录。若存在多个同名文件，工具会返回候选路径。所有附件读取
都被限制在对应 Skill 目录内部。

模型也可以根据用户的自然语言要求创建新 Skill：

```text
createSkill(name="pdf-tools", skillContext="---\nname: pdf-tools\ndescription: 处理 PDF 文件。\n---\n\n# PDF 工具\n\n...")
```

工具会把名称规范为小写字母、数字和连字符，在 `.agents/skills/` 下创建对应
子目录，并生成带 YAML Frontmatter 的 `SKILL.md`。如果同名 Skill 已存在，
工具会返回错误且不覆盖原内容。`references/`、`scripts/` 等辅助目录可在创建
成功后继续通过文件工具添加。

### searchWeb

`searchWeb(query)` 调用百度千帆的
[百度搜索 API](https://cloud.baidu.com/doc/qianfan-api/s/Wmbq4z7e5)，返回
搜索结果摘要以及参考来源的标题、URL、日期等信息。API Key 从 `config.ini`
的 `[search] baidu_api_key`（或环境变量 `BAIDU_SEARCH_API_KEY`）读取，
不会硬编码在代码中。网络失败、API 错误和缺少配置都会以
`{"error": ...}` 的形式返回给模型。

### fetchweb

`fetchweb(url)` 使用 `subprocess` 调用本地 `curl` 下载 HTML，再通过
`trafilatura` 提取正文并转换为 Markdown。工具会保留标题、段落、列表、表格和
链接，去除导航栏、广告、页脚等噪声内容，只把正文和原始 URL 返回给模型，减少
上下文 Token 消耗。

安全限制：

- 相对路径基于当前工作目录解析，支持 `~`
- `[files] confine_to_workspace = true`（默认）时，路径必须落在工作目录内，
  越界返回 `PATH_OUTSIDE_WORKSPACE`；改成 `false` 才允许跨目录
- 文本读取上限 2 MB，拒绝二进制文件
- 删除目录时禁止磁盘根目录、用户主目录、当前工作目录及其父目录
- 所有错误统一返回 JSON `{"error": ..., "code": ...}` 给模型

## 新增前端（Web / Desktop）

1. 新建 `web/` 或 `desktop/` 目录。
2. 用 `Settings.load()` 初始化配置，用 `ChatAgent(settings)` 创建 Agent。
3. 消费 `async for event in agent.send(text)`，把事件映射为该平台的输出：
   - Web：`TextDelta` → SSE/WebSocket 帧
   - Desktop：`TextDelta` → Qt/信号槽
4. 不要复制工具实现，也不要直接导入 `core.agent` 内部字段；只使用
   `core` 的公开接口与事件类型。

如果需要新增工具，只在 `core/tools` 中实现，并在
`build_default_registry()` 中注册，所有前端自动获得该能力。
