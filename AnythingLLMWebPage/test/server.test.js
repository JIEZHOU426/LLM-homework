/**
 * 代理行为集成测试：起一个假 AnythingLLM，验证"上传 → 向量化"两步闭环，
 * 以及请求头透传、错误归一化、工作区标识校验。
 *
 *   node --test test/
 */

const test = require('node:test');
const assert = require('node:assert/strict');
const http = require('http');

// server.js 在 import 时读取环境变量：先用占位值，等假上游起来后再重新加载
process.env.ANYTHINGLLM_BASE_URL = 'http://127.0.0.1:0';
process.env.ANYTHINGLLM_API_KEY = 'test-key';

let upstream;
let upstreamPort;
let app;

function handleUpstream(req, res) {
  let raw = '';
  req.on('data', (chunk) => { raw += chunk; });
  req.on('end', () => {
    upstream.calls.push({ method: req.method, url: req.url, headers: req.headers, body: raw });
    res.setHeader('Content-Type', 'application/json');
    if (req.url === '/api/v1/document/upload') {
      res.end(JSON.stringify({ success: true, documents: [{ location: 'custom-documents/notes.md-abc.json' }] }));
    } else if (/\/api\/v1\/workspace\/.+\/update-embeddings$/.test(req.url)) {
      res.end(JSON.stringify({ success: true, message: 'embeddings updated' }));
    } else if (req.url === '/api/v1/workspaces') {
      res.end(JSON.stringify({ workspaces: [{ id: 1, name: '课程', slug: 'course' }] }));
    } else {
      res.statusCode = 404;
      res.end(JSON.stringify({ error: `no route ${req.url}` }));
    }
  });
}

function startUpstream() {
  upstream = http.createServer(handleUpstream);
  upstream.calls = [];
  return new Promise((done) => upstream.listen(0, '127.0.0.1', done));
}

function request(pathname, options = {}) {
  return new Promise((resolve, reject) => {
    const { method = 'GET', headers = {}, body } = options;
    const req = http.request(
      { host: '127.0.0.1', port: app.address().port, path: pathname, method, headers },
      (res) => {
        let raw = '';
        res.on('data', (chunk) => { raw += chunk; });
        res.on('end', () => {
          let json = null;
          try { json = raw ? JSON.parse(raw) : null; } catch (e) { json = null; }
          resolve({ status: res.statusCode, json, raw });
        });
      }
    );
    req.on('error', reject);
    if (body !== undefined) req.write(body);
    req.end();
  });
}

test.before(async () => {
  await startUpstream();
  process.env.ANYTHINGLLM_BASE_URL = `http://127.0.0.1:${upstream.address().port}`;
  // require 之后再改环境变量无效，所以这里用相对模块路径直接构造：server.js 读的是常量，
  // 为让测试指向假上游，重新加载模块
  delete require.cache[require.resolve('../server.js')];
  delete require.cache[require.resolve('../lib.js')];
  app = require('../server.js').server;
  await new Promise((done) => app.listen(0, '127.0.0.1', done));
});

test.after(async () => {
  // Node 22 的全局 agent 默认开启 keep-alive，不断开连接 close() 会一直等
  if (typeof app.closeAllConnections === 'function') app.closeAllConnections();
  if (typeof upstream.closeAllConnections === 'function') upstream.closeAllConnections();
  await new Promise((done) => app.close(done));
  await new Promise((done) => upstream.close(done));
});

test('上传接口回传 locations 且不透传 Cookie', async () => {
  upstream.calls.length = 0;
  const res = await request('/api/upload', {
    method: 'POST',
    headers: { 'content-type': 'multipart/form-data; boundary=x', cookie: 'session=secret' },
    body: 'BOUNDARY-PAYLOAD',
  });
  assert.equal(res.status, 200);
  assert.deepEqual(res.json.locations, ['custom-documents/notes.md-abc.json']);

  const call = upstream.calls[0];
  assert.equal(call.url, '/api/v1/document/upload');
  assert.equal(call.headers.authorization, 'Bearer test-key');
  assert.equal(call.headers.cookie, undefined, 'Cookie 不能被透传');
  assert.equal(call.body, 'BOUNDARY-PAYLOAD', '文件请求体应原样转发');
});

test('向量化接口把 adds 改写成上游需要的形式', async () => {
  upstream.calls.length = 0;
  const res = await request('/api/embed', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ slug: 'course', adds: ['custom-documents/notes.md-abc.json'] }),
  });
  assert.equal(res.status, 200);
  assert.equal(res.json.embedded, true);
  assert.equal(res.json.workspace, 'course');

  const call = upstream.calls[0];
  assert.equal(call.url, '/api/v1/workspace/course/update-embeddings');
  assert.deepEqual(JSON.parse(call.body), {
    adds: ['custom-documents/notes.md-abc.json'],
    deletes: [],
  });
});

test('非法工作区标识在发请求前被拒', async () => {
  upstream.calls.length = 0;
  const res = await request('/api/embed', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ slug: '../admin', adds: ['x.json'] }),
  });
  assert.equal(res.status, 400);
  assert.equal(res.json.code, 'BAD_WORKSPACE');
  assert.equal(upstream.calls.length, 0);
});

test('空 adds 直接报 NOTHING_TO_EMBED', async () => {
  const res = await request('/api/embed', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ slug: 'course', adds: [] }),
  });
  assert.equal(res.status, 400);
  assert.equal(res.json.code, 'NOTHING_TO_EMBED');
});

test('上游错误归一化为 code + error', async () => {
  const res = await request('/api/v1/unknown');
  assert.equal(res.status, 404);
  assert.equal(res.json.code, 'NOT_FOUND');
});

test('静态文件不能跳出根目录', async () => {
  const res = await request('/../server.js');
  assert.equal(res.status, 403);
});
