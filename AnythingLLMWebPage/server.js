/**
 * AnythingLLM 本地代理服务。
 *
 * 浏览器只和本服务打交道，API Key 只在服务端使用：
 *   POST /api/upload         → POST /api/v1/document/upload
 *   POST /api/embed          → POST /api/v1/workspace/{slug}/update-embeddings
 *   GET  /api/workspaces     → GET  /api/v1/workspaces
 *   GET  /api/health         → 配置是否就绪
 *
 * 设计要点：
 * - 只转发 content-type / content-length / accept 三个请求头，Cookie、Origin、
 *   Referer、客户端的 Authorization 一律不透传；
 * - 工作区 slug 先过白名单再拼 URL；
 * - 静态文件用 path.relative 判定越界，避免读走同级目录；
 * - 上游错误统一成 { success:false, code, error }，前端按 code 提示。
 */

const http = require('http');
const https = require('https');
const fs = require('fs');
const path = require('path');

const {
  isSafeSlug,
  locationsFromUpload,
  pickProxyHeaders,
  resolveStaticPath,
  errorBody,
} = require('./lib');

const ROOT = __dirname;
const PORT = Number(process.env.PORT || 8080);

function loadEnv() {
  const candidates = [
    process.env.ENV_FILE,
    path.join(ROOT, '.env'),
    path.join(ROOT, '..', 'AnythingLLMMCP', 'anything_mcp', '.env'),
    path.join(ROOT, '..', 'AnythingLLMMCP', '.env'),
  ].filter(Boolean);

  for (const file of candidates) {
    if (!fs.existsSync(file)) continue;
    const text = fs.readFileSync(file, 'utf8');
    for (const line of text.split(/\r?\n/)) {
      const m = line.match(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$/);
      if (!m) continue;
      process.env[m[1]] = process.env[m[1]] || m[2].replace(/^["']|["']$/g, '');
    }
    return file;
  }
  return null;
}

const envFile = loadEnv();
const BASE_URL = (process.env.ANYTHINGLLM_BASE_URL || 'http://localhost:3001').replace(/\/+$/, '');
const API_KEY = process.env.ANYTHINGLLM_API_KEY || '';
const TIMEOUT_MS = Number(process.env.ANYTHINGLLM_TIMEOUT_MS || 60000);

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.ico': 'image/x-icon',
};

if (/server\.js$/.test(require.main ? require.main.filename : '') && !API_KEY) {
  console.error('缺少 ANYTHINGLLM_API_KEY：请在环境变量、本目录 .env 或 AnythingLLMMCP/.env 中配置');
  process.exit(1);
}

console.log(`配置来源: ${envFile || '环境变量'}`);
console.log(`AnythingLLM: ${BASE_URL}`);
console.log(`本地代理: http://localhost:${PORT}/upload.html`);

function sendJson(res, status, payload) {
  const body = JSON.stringify(payload);
  res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8' });
  res.end(body);
}

/**
 * 统一的代理出口：负责鉴权头、超时、错误归一化。
 *
 * body 为字符串时直接发送该请求体（用于把前端 JSON 改写成上游需要的形式），
 * 为 null 时把浏览器请求体原样 pipe 过去（用于文件上传）。
 */
function proxy(req, res, targetPath, options = {}) {
  const { body = null, onSuccess, code, method = req.method } = options;
  let target;
  try {
    target = new URL(targetPath, BASE_URL);
  } catch (e) {
    return sendJson(res, 500, errorBody('BAD_TARGET', `上游地址不合法: ${targetPath}`));
  }
  const client = target.protocol === 'https:' ? https : http;

  const headers = pickProxyHeaders(options.headers || req.headers);
  headers.host = target.host;
  headers.authorization = `Bearer ${API_KEY}`;
  if (body !== null) headers['content-length'] = Buffer.byteLength(body);

  const upstream = client.request(target, { method, headers }, (upRes) => {
    let raw = '';
    upRes.on('data', (chunk) => { raw += chunk; });
    upRes.on('end', () => {
      let data = null;
      try {
        data = raw ? JSON.parse(raw) : null;
      } catch (e) {
        data = null;
      }
      if (upRes.statusCode >= 200 && upRes.statusCode < 300) {
        return sendJson(res, 200, onSuccess ? onSuccess(data || {}) : data || {});
      }
      // 失败时不让整页 HTML 透传到前端
      const message =
        (data && (data.error || data.message)) || raw.slice(0, 160) || `HTTP ${upRes.statusCode}`;
      sendJson(res, upRes.statusCode || 502, errorBody(code || 'UPSTREAM_HTTP_ERROR', message));
    });
  });

  upstream.setTimeout(TIMEOUT_MS, () => {
    upstream.destroy(new Error(`上游 ${TIMEOUT_MS}ms 内未响应`));
  });
  upstream.on('error', (err) => {
    if (res.headersSent) return;
    sendJson(res, 502, errorBody('UPSTREAM_UNREACHABLE', `无法连接 AnythingLLM: ${err.message}`));
  });

  if (body !== null) {
    upstream.end(body);
  } else if (method === 'GET' || method === 'HEAD') {
    upstream.end();
  } else {
    req.pipe(upstream);
  }
}

function serveStatic(req, res) {
  let urlPath = (req.url || '/').split('?')[0];
  if (urlPath === '/') urlPath = '/upload.html';

  let filePath;
  try {
    filePath = resolveStaticPath(ROOT, urlPath);
  } catch (e) {
    filePath = null;
  }
  if (!filePath) {
    res.writeHead(403, { 'Content-Type': 'text/plain; charset=utf-8' });
    res.end('Forbidden');
    return;
  }

  fs.readFile(filePath, (err, data) => {
    if (err) {
      res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
      res.end('Not Found');
      return;
    }
    res.writeHead(200, {
      'Content-Type': MIME[path.extname(filePath).toLowerCase()] || 'application/octet-stream',
    });
    res.end(data);
  });
}

function readJsonBody(req) {
  return new Promise((resolve, reject) => {
    let raw = '';
    req.on('data', (chunk) => {
      raw += chunk;
      if (raw.length > 1 << 20) reject(new Error('请求体过大'));
    });
    req.on('end', () => {
      try {
        resolve(raw ? JSON.parse(raw) : {});
      } catch (e) {
        reject(new Error('请求体不是合法 JSON'));
      }
    });
    req.on('error', reject);
  });
}

const server = http.createServer((req, res) => {
  const urlPath = (req.url || '/').split('?')[0];

  if (urlPath === '/api/health' && req.method === 'GET') {
    return sendJson(res, 200, { success: true, baseUrl: BASE_URL, envFile });
  }

  // 第一步：上传文件（AnythingLLM 只做上传，不会自动向量化）
  if (urlPath === '/api/upload' && req.method === 'POST') {
    return proxy(req, res, '/api/v1/document/upload', {
      code: 'UPLOAD_FAILED',
      onSuccess: (data) => ({
        success: true,
        raw: data,
        // 关键：把"可向量化的 location"显式返回，前端不必猜上游结构
        locations: locationsFromUpload(data),
      }),
    });
  }

  // 第二步：把一个或多个文档位置提交向量化（上传不会自动入库）
  if (urlPath === '/api/embed' && req.method === 'POST') {
    return readJsonBody(req)
      .then((body) => {
        const slug = String(body.slug || '').trim();
        if (!isSafeSlug(slug)) {
          return sendJson(res, 400, errorBody('BAD_WORKSPACE', `工作区标识不合法: ${slug || '(空)'}`));
        }
        const adds = Array.isArray(body.adds)
          ? body.adds.filter((x) => typeof x === 'string' && x.trim())
          : [];
        if (!adds.length) {
          return sendJson(res, 400, errorBody('NOTHING_TO_EMBED', '没有可向量化的文档位置'));
        }
        const deletes = Array.isArray(body.deletes)
          ? body.deletes.filter((x) => typeof x === 'string')
          : [];
        return proxy(req, res, `/api/v1/workspace/${encodeURIComponent(slug)}/update-embeddings`, {
          code: 'EMBED_FAILED',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ adds, deletes }),
          onSuccess: (data) => ({
            success: true,
            workspace: slug,
            embedded: data.success !== false,
            message: data.message || 'embeddings updated',
            raw: data,
          }),
        });
      })
      .catch((err) => sendJson(res, 400, errorBody('BAD_REQUEST', err.message)));
  }

  if (urlPath === '/api/workspaces' && req.method === 'GET') {
    return proxy(req, res, '/api/v1/workspaces', { code: 'WORKSPACES_FAILED' });
  }

  if (urlPath.startsWith('/api/')) {
    return sendJson(res, 404, errorBody('NOT_FOUND', '未知接口'));
  }
  if (req.method !== 'GET' && req.method !== 'HEAD') {
    res.writeHead(405, { 'Content-Type': 'text/plain; charset=utf-8' });
    res.end('Method Not Allowed');
    return;
  }
  serveStatic(req, res);
});

if (require.main === module) {
  server.listen(PORT, () => {
    console.log(`打开 http://localhost:${PORT}/upload.html`);
  });
}

module.exports = { server, BASE_URL, API_KEY, envFile };
