# LLM 仓库评分报告

## 评分范围

- 仓库：`https://github.com/JIEZHOU426/LLM-homework.git`（本地 `D:\LLM`，当前分支 `师傅`，HEAD `344aa93`，共 4 个提交；`origin/master` 比本机 HEAD 还落后 3 个提交）
- 评分对象：**当前工作区文件树**（HEAD 344aa93 + 65 个文件的未提交改动，其中 12 个为新增未跟踪文件：根 `README.md`、`AGENT.md`、全部 `tests/`、`.github/workflows/ci.yml`、`lib.js`、`call_log.py` 等）
- 理由：工作区是你能看到的最新交付态，GitHub 上的 `master` 反而更旧；提交态与工作区的分差在文末单列，供你决定是否先提交。
- 只读约束：未修改任何仓库文件，未构建镜像，未改动依赖，未调用 `.env` 中的真实 Key。
- 为验证声明实跑：`python -m unittest` ×3 + `node --test` ×1，合计 **69 例，全绿**；并用程序枚举工具清单，不为"应约数字"跳过实测。

## 总分

| 维度 | 得分 | 满分 |
| --- | --- | --- |
| A 宠物医院 MCP | 9.5 | 10 |
| B AnythingLLM MCP | 8.5 | 10 |
| C AnythingLLM 网页 | 8.5 | 10 |
| D 定制 Agent | 49.5 | 50 |
| E 顶层 README 与复现 | 9.5 | 10 |
| F 文档代码一致性 | 9.0 | 10 |
| **基础分** | **94.5** | **100** |
| G 亮点 | +10（原始 14，封顶） | +10 |
| **最终** | **104.5** | **110** |
| 等级 | **优秀** | |

四个模块均 ≥85%（良好及以上），不触发降档；无造假与安全红线。

## 维度评分

### A 宠物医院 MCP — 9.5/10

- **A1 协议符合性 3/3**：真 MCP 服务器，非 REST 二次封装。`PetHospitalMCP/chongwu_mcp/src/pet_hospital_mcp/__init__.py:28` `MCPServer("PetHospital")`，`:342` `mcp.run()`（stdio）；`:187` `add_pet`、`:225` `get_pets` 两个 `@mcp.tool`；README 给了可粘贴的 `mcpServers` 配置与 `uv run python -m pet_hospital_mcp` 启动命令。已用已装 `mcp 2.3.0` 验证 `MCPServer` / `ToolError` 导入有效，不是纸面 API。
- **A2 工具契约 2/2**：`species` 枚举、`limit` 用 `Field(ge=1, le=50)` 约束，docstring 写明返回字段（`pets` 数组结构）。
- **A3 错误语义 2/2**：失败统一抛 `ToolError`，消息体为 JSON（`code`/`message`/`status`/`detail`），`:62-70`；上游 detail 截断，不把原始异常字符串丢给模型。
- **A4 工程配套 2/2**：`:99` `_request` 带超时、`:106` 有上限重试、stderr 结构化日志；`tests/test_tools.py` 9 例覆盖成功/空结果/超时/429/404（实测 `Ran 9 tests ... OK`）。
- **A5 文档 0.5/1**：端点、依赖、`.env.example`、调用示例、排错表都有；**但上游宠物医院后端的来源与启动方式、接口契约完全没写**——README 只有一句"调用工具前需要先启动宠物医院后端服务"（`:40`），别人无法从仓库复现这条链路。

### B AnythingLLM MCP — 8.5/10

- **B1 4/4**：真 MCP 服务器（`src/mcp_anythingllm/server.py`，`mcp 2.3.0`），Streamable HTTP 由 `uvicorn` 拉起 `/mcp`；4 个工具可被客户端枚举（`tests/test_client.py` 的 `list_tools` 断言，实测 13 例通过）。
- **B2 3/3**：覆盖 4 类能力——`list_workspaces`（GET `/api/v1/workspaces`）、`workspace_chat`（POST `/api/v1/openai/chat/completions`）、`upload_and_embed_document`（upload + update-embeddings 两步合一，避免"只传不 embed"）、`vector_search`（vector-search，返回片段与相似度）。
- **B3 2/2**：Key 从 `ANYTHINGLLM_API_KEY`/`.env` 读，模板值为占位符；缺 Key 在发请求前直接 `CONFIG_ERROR`，不泄漏；slug 有正则校验。
- **B4 1/1**：启动命令、客户端配置示例、失败场景表齐全。
- **未进优秀档**：无分块管理（chunk 列表/更新/删除）、无分页，`list_workspaces` 一次全返。

### C AnythingLLM 网页 — 8.5/10

- **C1 4/4**：真实闭环——`upload.html` 选文件 → `POST /api/upload` → `POST /api/embed`，页面三态齐备（进行中禁用按钮+进度文案、成功展示 `documents.location` 与已入库提示、失败展示后端错误码）。
- **C2 2/2**：`server.js` 代理 `/api/health`、`/api/upload`、`/api/embed`、`/api/workspaces` 到 `/api/v1/...`；鉴权头、multipart 请求体与 AnythingLLM 契约一致；工作区列表取自 `GET /api/v1/workspaces` 并渲染下拉框，非硬编码。
- **C3 2/2**：职责已拆分（`lib.js` 抽纯函数、`test/` 下 11 例单测+代理集成测试，含随机端口真实 HTTP 往返）；`viewport` + `max-width` 适配窄屏。
- **C4 2/2**：Key 只在服务端环境变量，前端零密钥；DOM 用 `textContent` 写入，无 XSS；路径白名单 + 防目录穿越。
- **未进优秀档**：无流式对话、无多轮上下文（页面只做"上传+向量化"这一条主流程）。

### D 定制 Agent（qAgent）— 49.5/50

- **D1 工具调用闭环 6/6**：`core/agent.py:258 send()` → 流式收 `delta.tool_calls` → `_execute_tool` → 结果以 `role:"tool"` 回填 → 再请求，闭环；`:285` 达 `max_steps` 停止、`:281` `turn_timeout` 截止、`:294` 超时文案；工具错误以 JSON 作为 tool 结果返给模型可自纠。`tests/test_turn_guard.py` 用假流断言"一直要工具"会被截停且 tool 消息 ≤ 3 条。
- **D2 4/4**：`getDate` 走 `date`/`time` 系统命令（跨平台、非硬编码）；`isleapyear` 用 `%4==0 and (%100!=0 or %400==0)`，`test_clock.py` 覆盖 2024/1900/2000/2023。
- **D3 5/5**：10 类语义全覆盖且都是真边界函数，不是名字对不上实现的空壳——`filesystem.py:253/256/290/325/342/365/394/403/417/431` 依次为 cwd、列表、类型、读文本、建文件（已存在即拒绝）、改写/追加、建目录、删目录（清空+保护）、删文件（对目录报错并提示正确工具）、改名；`_string_argument` 缺参报"缺少参数"，`PATH_OUTSIDE_WORKSPACE` 拦越界与相对路径逃逸（`test_filesystem.py:118-133`）。
- **D4a 10/10**：`fetchweb` 真取网（`subprocess` curl + trafilatura 提正文，超时/异常结构化返回）；`searchWeb` 真调百度千帆 `qianfan.baidubce.com/v2/ai_search/web_search`，Key 缺失时给配置指引。
- **D4b 10/10**：技能四件套齐全——`skills.py:142 create` 落盘目录+SKILL.md+YAML frontmatter、`:37` 拒绝重名覆盖、`:62 discover` 启动只读 name/description 注入系统提示、`:120 load` 按需读正文且附件路径锁在技能目录内（越界被拒，`test_skills.py:68-73`）。
- **D5 4.5/5**：`mcp_client.py:195` 读工作目录 `.mcp.json`、`:292` stdio 与 Streamable HTTP 双分支、`:327` schema→`ToolSpec` 并入统一注册表、状态/失败进边栏并降级继续（连接超时 20s、调用 120s）。扣 0.5：`:44 SSE_TYPES` 只声明、无 SSE client 分支（`sse` 会走到"传输类型不支持"）。
- **D6 6/6**：`agents_md.py` 启动整读一次、作为单条 system 消息注入（`agent.py:203/221`，恢复会话用持久化内容而非重读）、超 1MB 截断、缺失静默、文件名经 `[agents] filename`/`QAGENT_AGENTS_FILE` 可配、`AGENT.md` 与 `AGENTS.md` 互为别名；README 与 `AGENT.md` 均写明"一次注入、全程复用、不破坏 prompt cache"。
- **D7 4/4**：会话 JSONL 事件日志与 `/resume` 恢复（`sessions.py`）、`/compact` 压缩+原文归档+`recallContext` 全文检索（`compact.py`、`tools/recall.py`）、工具调用结构化日志（`call_log.py`，只记参数名不记值）、36 例单测实测全通过。

### E 顶层 README 与复现 — 9.5/10

- **E1 4/4**：模块地图 + ASCII 数据流（`:34`）+ 依赖关系（AnythingLLM `:3001`、宠物医院 `:8080`、DeepSeek）+ 逐模块配置 + 带序号的启动与验证清单。
- **E2 3/3**：A/B/C/D 各有独立 README，含配置项、用法、排错；`PetHospitalMCP/chongwu_mcp/mcp.md` 另给协议说明。
- **E3 1/1**：`.env.example`×3、`config.ini.example`、`miniapp` 字段表齐全，真实 Key 未入库（`git log -S` 检索为空）。
- **E4 1.5/2**：版本约束（`requires-python>=3.10`、`mcp>=2.0`、Node 20）与上游前置（AnythingLLM、DeepSeek）已写；扣 0.5——宠物医院后端的部署/启动步骤缺失，"能跑的环境"只剩假设。

### F 文档代码一致性 — 9.0/10

- **F1 2.5/3**：工具数量与 `程序枚举` 完全一致（qAgent 17 个，实测 17；宠物医院 2；AnythingLLM 4）；用例数 36/9/13/11 与实测逐项吻合。扣 0.5——模块规模列陈旧：根 README 写"网页 2 个文件/约 490 行"，实际 3 个（`lib.js` 后加）、575 行；qAgent 写"36 个 Python 文件"，实际 37 个源码文件（45 含 tests）。
- **F2 2/2**：`config.ini.example` 的 9 个 section 与 `config.py` 读取键一一对应；端口 8000/3001/8080 在各 README 一致。
- **F3 2/2**：宣称的流式、重试、截断、向量化、路径边界全部在代码中可定位，无"说了没做"。
- **F4 0.5/1**：扣 0.5——`AnythingLLMMCP/anything_mcp/.mcp.json` 用 `command: py run.py` 以 stdio 启动一个 HTTP 服务，与本目录 README"必须写 url、不能写 command"直接矛盾（已被 gitignore，未入库）。
- **F5 2/2**：各 README 目录树与仓库实际一致（含 `tests/`、`lib.js`、`test/`）；工具日志示例字段与 `call_log.py` 输出格式一致。

## 亮点与扣分

### 加分（原始 14，封顶 10）

| 类别 | 位置 | 阈值 | 实测值 |
| --- | --- | --- | --- |
| 会话持久化与恢复 +2 | `core/sessions.py`、`tui/app.py:463-494` | 断点续聊可用 | `/resume` 列表 + 原样回放，agents_md 一并复原 |
| 上下文压缩 +2 | `core/compact.py:409`(compact)、`tools/recall.py` | 阈值触发 | 0.6 阈值告警→摘要 5000 tokens→原文归档→`recallContext` 可检索 |
| TUI 交互 +2 | `tui/app.py`(772 行)、`tui/widgets/` | 可连续对话 | 斜杠命令、MCP 边栏、压缩面板、配置引导 |
| 单测有断言 +2 | 4 套 `tests/` | ≥断言非快照 | 69 例全绿，断言具体产物（含文件内容比对、越界拒绝） |
| 安全设计 +2 | `filesystem.py:55`、`mcp_anythingllm/config.py` | 路径白名单+危险操作保护 | `confine_to_workspace`、根目录删除保护、slug 校验、Key 分级 |
| CI +1（原 +2） | `.github/workflows/ci.yml` | 真实 workflow | 4 job 全在；但 `on.push.branches=[main,master]`，当前分支为 `师傅`，不推 master 则不触发 |
| 结构化日志 +1 | `core/call_log.py` | 落盘可查 | JSONL，含 `dur_ms`/`code`，只记参数名 |
| 超时与重试 +1 | `pet_hospital_mcp/__init__.py:99`、`mcp_client.py:195` | 有上限 | 后端重试 3 次、MCP 连接 20s/调用 120s、单轮 600s |
| 多 MCP 隔离 +1 | `mcp_client.py:327` | 来源可区分 | 重名才加 server 前缀（部分实现） |
| 架构图/决策记录 +1 | `chat_file_architecture.mmd`、`AnythingLLMMCP/anything_mcp/MVP_DEVELOPMENT_PLAN.md` | 与代码对得上 | 数据流图与端点一致；计划文档列"与早期计划的差异" |
| 技能渐进加载 +1 | `skills.py:62/100/120` | 只注名称描述 | 启动只注 name+description，正文按需 load |

排除项：无整目录复制的第三方技能包，无与代码不符的 AI 升级提示，无缓存/虚拟环境入库（均为 gitignore 状态）。

### 扣分

| 扣分项 | 分值 |
| --- | --- |
| A5 上游宠物医院后端来源/启动/接口契约未文档化 | −0.5 |
| E4 同上（复现条件只剩假设） | −0.5 |
| B 缺分块管理与分页，未进优秀档 | −1.5 |
| C 无流式对话/多轮上下文，未进优秀档 | −1.5 |
| D5 SSE 传输类型声明未实现 | −0.5 |
| F1 模块规模数字陈旧（网页 2→3 文件、qAgent 36→37） | −0.5 |
| F4 遗留 `.mcp.json` 与 README 传输方式矛盾 | −0.5 |
| **合计** | **−5.5** |

## 六个问题

1. **最薄弱环节**：B、C 的能力纵深，不是代码质量。B 少"分块管理/分页"，C 少"流式对话/多轮上下文"，恰好是优秀档的分界条件。
2. **写而未接 / 声称未实现 / 跑不通 / 文档超代码**：①`mcp_client.py:44` 声明 `sse` 却无 client 分支，传 `type:"sse"` 直接报"传输类型不支持"；②技能生态只做了"渐进加载"，README 未夸大，但缺示例技能与校验脚本；③宠物医院后端无部署文档，别人跑到 A2 就开始报连接失败；④模块规模数字小于实际（属"文档落后于代码"的反向，观感好于虚报）。
3. **名不副实**：没有。`recallContext` 是全文关键词检索而非语义检索，README 与 docstring 都如实写"无 embedding、无向量库"，属诚实命名。最像"有但没生效"的是 CI：workflow 真实存在，但触发分支是 `master`，而实际工作在 `师傅` 分支，只在 GitHub 上看会以为"每次提交都被测过"。
4. **删测试 / 伪造运行记录**：无。69 例均实跑通过，断言到具体产物（`test_filesystem.py:48` 比对文件内容、`:121` 断言越界码）；文档里的 36/9/13/11 与实测逐项吻合，属真实证据而非补写的"通过"。
5. **只给 2 小时补什么**：先删工作区 3 个 `.env` 并吊销那枚真实 Key → 把 65 个未提交改动提交并推送（否则 GitHub 上是旧版）→ 补宠物医院后端启动与接口契约 → 改 CI 触发分支。这四步不加功能，但直接决定"能不能被别人跑起来、会不会泄密"，合计 +1.0 分并消掉最大风险。
6. **投入度证据**（10 行内）：①4 套测试 69 例且断言具体行为，不是占位；②`agent.py` 分事件流/循环/压缩三层，`tui` 再抽 8 个 widget，是有意分层不是堆文件；③`config.ini.example` 9 个 section 与 `config.py` 逐键对齐，说明配置是设计出来的；④每个模块 README 都有排错表与"边界能做什么/不能做什么"；⑤`AGENT.md` 写"删除、覆盖前必须先说明路径"，把安全习惯写进了项目约定；⑥`MVP_DEVELOPMENT_PLAN.md` 主动列"与早期计划的差异"，删掉了调试脚本；⑦MCP 双向都做了（既做 server 又做 client）；⑧`.gitignore` 分层到每个子项目，`.env`/`.mcp.json`/`.agents` 都排除了。结论：明显是一个人在持续多轮上叠加真实工作，不是最后一晚拼装。

## 风险

| 项 | 有/无 | 位置 |
| --- | --- | --- |
| 硬编码密钥 | 仓库内无；**磁盘上有** | `Agent/qAgent/.env`、`AnythingLLMMCP/.env`、`AnythingLLMMCP/anything_mcp/.env` 存同一枚真实 DeepSeek Key（`sk-` 开头，此处不复述）。已被 `.gitignore` 排除且 `git log -S` 确认未进历史；但**以文件夹压缩包形式提交就会泄露**，建议提交前吊销重签 |
| prompt 注入/越权 | 有边界 | MCP 工具同名仅加前缀（`mcp_client.py:327`），来源标记不完整；`AGENT.md` 属项目内可信内容，未做来源隔离 |
| 路径/用户输入校验 | 有 | `filesystem.py:55` `ensure_within`；前端 slug 白名单；后端 slug 正则 |
| 危险操作 | 有保护 | `ensure_safe_delete` 拒绝删根/工作目录；`delete_file` 对目录给出正确工具提示 |
| 隐私 | 低风险 | 会话/工具日志落本地 `.agents/`；`fetchweb` 只回正文；无第三方上报 |
| 缓存入库 | 无（但磁盘有） | `__pycache__`、`*.egg-info`、`.venv` 存在且被忽略；`uv.lock`×2（约 190KB/207KB）已入库，属正常 |
| 遗留配置 | 有 | 根 `.mcp.json` 只挂第三方 `Bazi-MCP` 远端（未文档化）；`anything_mcp/.mcp.json` 传输方式写错。两者均被 gitignore，未交付 |

## 提交态差异（供你决策）

若严格按 **commit `344aa93`** 计分，该快照缺：根 `README.md`、`AGENT.md`、全部 `tests/`、`.github/`、`lib.js`、`call_log.py`、`recallContext`，且含 `AnythingLLMMCP/chongwu_mcp`、`AnythingLLMMCP/Project1` 两份重复嵌套副本。对应 E1（−3.5）、D6（−6）、D7（−1）、F1（−1）、G（−4~6）将大面积归零，基础分落到 **78–82（良好）**；而 GitHub 上的 `master` 比 HEAD 还旧 3 个提交。结论：**当前工作区是真交付，GitHub 上是旧交付**，提交前请以工作区为准。

## 改进优先级

| 优先级 | 问题 | 位置 | 补法 | 收益 |
| --- | --- | --- | --- | --- |
| P0 | 真实 Key 留在磁盘 3 处 | 各 `.env` | 吊销重签，只留 `sk-your-...` 占位 | 消掉最大风险 |
| P0 | 65 个改动未提交、GitHub 落后 | 仓库根 | 提交 + 推送，或确认以工作区交付 | 决定 E1/D6/D7/G 是否归零 |
| P1 | 宠物医院后端无法复现 | `chongwu_mcp/README.md:40` | 补获取方式、启动命令、接口契约（GET /pets 参数与返回） | A5+E4 +1.0 |
| P1 | CI 分支错位 | `.github/workflows/ci.yml:5` | `branches: [main, master, 师傅]` 或统一主干名 | 让 CI 真的跑起来 |
| P2 | B 缺分块管理与分页 | `mcp_anythingllm/server.py` | 加 `list/update/delete chunks` 与 `limit/offset` | B 8.5→9.5 |
| P2 | C 无流式与多轮 | `upload.html`、`server.js` | 加对话面板走 SSE 转发 `/api/v1/openai/chat/completions` | C 8.5→9.5 |
| P2 | D5 SSE 声明未实现 | `mcp_client.py:44` | 删常量，或补 sse client 分支；来源前缀改为始终加 | D5 4.5→5 |
| P3 | 模块规模数字陈旧 | 根 `README.md` 表 | 按实际 3 文件/575 行、37 文件/6190 行更新 | F1 2.5→3 |
| P3 | 遗留 `.mcp.json` 矛盾 | `anything_mcp/.mcp.json` | 改为 `url: http://127.0.0.1:8000/mcp` 或删除 | F4 0.5→1 |
| P3 | 技能生态只有渐进加载 | `.agents/skills/` | 加 1 个示例技能 + 校验脚本 | G 技能项补齐（当前已封顶） |
