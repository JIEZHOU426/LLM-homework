const http = require('http');
const https = require('https');
const fs = require('fs');
const path = require('path');

const ROOT = __dirname;
const PORT = Number(process.env.PORT || 8080);

function loadEnv() {
  const candidates = [
    process.env.ENV_FILE,
    path.join(ROOT, '.env'),
    path.join(ROOT, '..', 'AnythingLLMMCP', '.env')
  ].filter(Boolean);

  for (const file of candidates) {
    if (!fs.existsSync(file)) continue;
    const text = fs.readFileSync(file, 'utf8');
    for (const line of text.split(/\r?\n/)) {
      const m = line.match(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$/);
      if (!m) continue;
      const value = m[2].replace(/^["']|["']$/g, '');
      if (process.env[m[1]] === undefined) process.env[m[1]] = value;
    }
    return file;
  }
  return null;
}

const envFile = loadEnv();
const BASE_URL = (process.env.ANYTHINGLLM_BASE_URL || 'http://localhost:3001').replace(/\/+$/, '');
const API_KEY = process.env.ANYTHINGLLM_API_KEY || '';

if (!API_KEY) {
  console.error('缺少 ANYTHINGLLM_API_KEY，请设置环境变量或在 .env 中配置');
  process.exit(1);
}

console.log(`配置来源: ${envFile || '环境变量'}`);
console.log(`AnythingLLM: ${BASE_URL}`);

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.ico': 'image/x-icon'
};

function proxy(req, res, targetPath) {
  const target = new URL(targetPath, BASE_URL);
  const client = target.protocol === 'https:' ? https : http;

  const headers = { ...req.headers, host: target.host, authorization: `Bearer ${API_KEY}` };
  delete headers.origin;
  delete headers.referer;

  const upstream = client.request(target, { method: req.method, headers }, (upRes) => {
    res.writeHead(upRes.statusCode || 502, upRes.headers);
    upRes.pipe(res);
  });

  upstream.on('error', (err) => {
    if (!res.headersSent) res.writeHead(502, { 'Content-Type': 'application/json; charset=utf-8' });
    res.end(JSON.stringify({ success: false, error: `无法连接 AnythingLLM: ${err.message}` }));
  });

  if (req.method === 'GET' || req.method === 'HEAD') {
    upstream.end();
  } else {
    req.pipe(upstream);
  }
}

function serveStatic(req, res) {
  let urlPath = decodeURIComponent((req.url || '/').split('?')[0]);
  if (urlPath === '/') urlPath = '/upload.html';

  const filePath = path.join(ROOT, path.normalize(urlPath));
  if (!filePath.startsWith(ROOT)) {
    res.writeHead(403);
    res.end('Forbidden');
    return;
  }

  fs.readFile(filePath, (err, data) => {
    if (err) {
      res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
      res.end('Not Found');
      return;
    }
    res.writeHead(200, { 'Content-Type': MIME[path.extname(filePath).toLowerCase()] || 'application/octet-stream' });
    res.end(data);
  });
}

const server = http.createServer((req, res) => {
  const urlPath = (req.url || '/').split('?')[0];

  if (urlPath === '/api/upload' && req.method === 'POST') {
    return proxy(req, res, '/api/v1/document/upload');
  }
  if (urlPath === '/api/workspaces' && req.method === 'GET') {
    return proxy(req, res, '/api/v1/workspaces');
  }
  if (urlPath.startsWith('/api/')) {
    res.writeHead(404, { 'Content-Type': 'application/json; charset=utf-8' });
    res.end(JSON.stringify({ success: false, error: '未知接口' }));
    return;
  }
  if (req.method !== 'GET' && req.method !== 'HEAD') {
    res.writeHead(405);
    res.end('Method Not Allowed');
    return;
  }
  serveStatic(req, res);
});

server.listen(PORT, () => {
  console.log(`打开 http://localhost:${PORT}/upload.html`);
});
