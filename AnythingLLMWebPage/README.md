# AnythingLLMWebPage

上传文档到 AnythingLLM 的单页工具。API Key 由本地后端代理持有，浏览器端无需输入。

## 使用方法

1. 启动本地服务：

   ```powershell
   node server.js
   ```

2. 浏览器打开 http://localhost:8080/upload.html
3. 选择本地文件与目标工作区，点击「上传并嵌入」，文档会上传到本地 AnythingLLM 实例并加入指定工作区。

## 配置

后端按以下顺序读取配置（已存在的环境变量优先）：

1. 环境变量 `ENV_FILE` 指定的文件
2. 本目录 `.env`
3. `../AnythingLLMMCP/.env`（复用已有配置）

需要的变量：

```ini
ANYTHINGLLM_BASE_URL=http://localhost:3001
ANYTHINGLLM_API_KEY=your-developer-api-key
```

可选变量：

- `PORT`：本地服务端口，默认 `8080`

API Key 只在后端使用，不会返回给浏览器。请确保 `.env` 已被 git 忽略，不要提交密钥。

## 接口

- `POST /api/upload`：转发到 AnythingLLM `POST /api/v1/document/upload`
- `GET /api/workspaces`：转发到 AnythingLLM `GET /api/v1/workspaces`，用于填充工作区下拉框
