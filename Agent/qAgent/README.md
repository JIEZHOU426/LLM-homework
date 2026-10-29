# qAgent

基于 `Agent/Project2/chat_file.py` 改造的 DeepSeek Agent。业务逻辑与界面完全分离：
`core` 不依赖任何 UI，`tui` 只是其中一个前端实现。后续可以新增 `web`、`desktop`
等目录，复用同一套核心能力。

## 目录结构

```text
qAgent/
├── main.py                  # TUI 启动入口
├── requirements.txt
├── .env.example
├── config.ini.example
├── core/                    # 业务核心（禁止导入 tui / web / desktop）
│   ├── config.py            # Settings：读取 .env 与 config.ini
│   ├── events.py            # 核心向前端输出的事件协议
│   ├── agent.py             # ChatAgent：对话状态 + 流式 + 工具调用循环
│   ├── llm/
│   │   └── client.py        # OpenAI 兼容客户端构造
│   └── tools/
│       ├── base.py          # Tool / ToolSpec / FunctionTool 契约
│       ├── registry.py      # 注册、Schema 导出、参数校验与分发
│       ├── common.py        # 路径、编码、文本读取、删除保护
│       ├── clock.py         # getDate、isleapyear
│       ├── filesystem.py    # 10 个本地文件操作工具
│       ├── search.py        # searchWeb：百度千帆联网搜索
│       └── web.py           # fetchweb：网页正文抓取与 Markdown 转换
└── tui/                     # Textual 前端（只依赖 core 的公开接口）
    ├── app.py               # 组合根：把核心事件映射为界面行为
    ├── styles.tcss
    ├── __main__.py
    └── widgets/
        ├── chat.py          # ChatView / MessageCard
        ├── input.py         # ChatInput
        └── status.py        # StatusBar
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

配置 API Key（二选一）：

- 复制 `.env.example` 为 `.env`，填写 `DEEPSEEK_API_KEY`
- 复制 `config.ini.example` 为 `config.ini`，填写 `[LLM] api_key`

`.env` 优先级高于 `config.ini`。

使用联网搜索工具 `searchWeb` 还需要百度千帆 API Key，二选一：

- 在 `config.ini` 的 `[search]` 中填写 `baidu_api_key`
- 在 `.env` 中设置 `BAIDU_SEARCH_API_KEY`

未配置时程序仍可启动，只有调用 `searchWeb` 时才会向模型返回缺少配置的错误提示。

## TUI 操作

| 操作 | 说明 |
| --- | --- |
| `Enter` | 发送问题 |
| `/help` | 查看命令 |
| `/clear`、`/new` | 清空对话 |
| `/quit`、`/exit` | 退出 |
| `Ctrl+Q` | 退出 |
| `Ctrl+L` | 清空对话 |

## 工具

共 14 个：

- 时间与日期：`getDate`、`isleapyear`
- 文件与目录：`get_cwd`、`list_directory`、`get_file_type`、`read_text_file`、
  `create_file`、`edit_file`、`create_directory`、`delete_directory`、
  `delete_file`、`rename_path`
- 网页内容：`fetchweb`
- 联网搜索：`searchWeb`

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
- 文本读取上限 2 MB，拒绝二进制文件
- 删除目录时禁止磁盘根目录、用户主目录、当前工作目录及其父目录
- 所有错误统一返回 JSON `{"error": ...}` 给模型

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
