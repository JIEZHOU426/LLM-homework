# AnythingLLMWebPage

一个单页工具：把本地文件上传到 AnythingLLM 的指定工作区，**并完成向量化**，
让文档真正进入检索库。API Key 只存在于本地代理进程，浏览器永远拿不到。

## 为什么需要这一层代理

AnythingLLM 的 API 需要 Bearer Key。直接把 Key 写进前端等于公开密钥；因此本
项目用 Node 内置 `http` 起一个极薄的代理：

```text
浏览器 upload.html ──► localhost:8080 (server.js, 持有 API Key) ──► AnythingLLM:3001
```

## 使用

```bash
cd AnythingLLMWebPage
node server.js            # 或 npm start
# 浏览器打开 http://localhost:8080/upload.html
```

页面流程（三步，状态各自可见）：

1. **上传** → `POST /api/v1/document/upload`，返回文档 `location`；
2. **向量化** → `POST /api/v1/workspace/{slug}/update-embeddings`，
   `adds` 就是第一步拿到的 `location`；
3. **结果确认** → 显示 `embedded` 与 `message`，并把原始响应折叠展示。

只上传不 embed 的文件在 AnythingLLM 里检索不到，所以页面把两步串成一个按钮，
失败时会显示是哪一步失败、下一步该查什么（例如 `EMBED_FAILED` 指向 Embedded
模型配置）。

## 配置

读取顺序（已存在的环境变量优先，缺的才填）：

1. `ENV_FILE` 指定的文件；
2. 本目录 `.env`；
3. `../AnythingLLMMCP/anything_mcp/.env`；
4. `../AnythingLLMMCP/.env`。

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `ANYTHINGLLM_BASE_URL` | `http://localhost:3001` | AnythingLLM 地址 |
| `ANYTHINGLLM_API_KEY` | 无 | **必填**，缺失时进程直接退出并提示 |
| `PORT` | `8080` | 本地代理端口 |
| `ANYTHINGLLM_TIMEOUT_MS` | `60000` | 上游超时（向量化可能较慢） |

## 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/upload` | 转发文件到 `/api/v1/document/upload`，额外返回 `locations`（已解析的文档位置） |
| `POST` | `/api/embed` | 入参 `{slug, adds:[location]}`，转发到 `/api/v1/workspace/{slug}/update-embeddings` |
| `GET` | `/api/workspaces` | 转发 `/api/v1/workspaces`，用于填充下拉框 |
| `GET` | `/api/health` | 返回代理当前使用的 `baseUrl` 与配置来源，用于排查 |

失败统一为 `{ "success": false, "code": "...", "error": "..." }`，前端按 `code`
给出针对性提示（`BAD_WORKSPACE` / `NOTHING_TO_EMBED` / `UPLOAD_FAILED` /
`EMBED_FAILED` / `UPSTREAM_UNREACHABLE`）。

## 安全措施

- **请求头白名单**：只转发 `content-type` / `content-length` / `accept`；
  浏览器的 `Cookie`（会话凭证）、`Origin`、`Referer` 以及客户端自带的
  `Authorization` 一律不转发（`lib.js:pickProxyHeaders` + 单元测试覆盖）；
- **工作区标识白名单**：`slug` 会拼进上游 URL，先过正则（字母数字、点、下划线、
  连字符，字母数字开头）再发请求，`../admin` 这类输入直接被 400 拒绝；
- **静态文件边界**：`path.relative` 判定，且显式拒绝含 `..` 段或盘符的路径；
- **前端不拼 HTML**：工作区下拉框用 `createElement` + `textContent` 构建
  （旧版把工作区名字拼进 `innerHTML`，工作区名可被写入脚本）；
- 上游错误体不整段回传浏览器，只取 `error` / `message` 字段或截断文本。

## 测试

```bash
node --test          # 11 个用例：5 个纯函数 + 6 个代理集成
```

- `test/lib.test.js`：slug 白名单、上传响应三种形状、请求头剔除、路径越界；
- `test/server.test.js`：起假 AnythingLLM 上游，验证"上传→拿到 location→
  向量化携带 adds"的完整链路、Cookie 不泄漏、非法 slug 在发请求前被拒、
  错误归一化、静态文件越界 403。

## 文件

```text
AnythingLLMWebPage/
├── server.js            # 代理 + 静态服务
├── lib.js               # 纯函数（白名单 / 响应解析 / 路径解析）
├── upload.html          # 三步式上传页面
├── package.json
├── README.md
└── test/
    ├── lib.test.js
    └── server.test.js
```
