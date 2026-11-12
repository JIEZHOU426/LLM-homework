/**
 * lib.js 纯函数测试：node --test test/
 */

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');

const lib = require('../lib');

test('isSafeSlug 只接受白名单标识', () => {
  assert.equal(lib.isSafeSlug('course'), true);
  assert.equal(lib.isSafeSlug('my-workspace_1.md'), true);
  assert.equal(lib.isSafeSlug('  course  '), true);
  for (const bad of ['../admin', 'a b', '', null, 'x'.repeat(80), '/etc/passwd', '工作区']) {
    assert.equal(lib.isSafeSlug(bad), false, `应拒绝: ${bad}`);
  }
});

test('locationsFromUpload 兼容三种响应形状', () => {
  assert.deepEqual(
    lib.locationsFromUpload({ documents: [{ location: 'custom-documents/a.md-1.json' }] }),
    ['custom-documents/a.md-1.json']
  );
  assert.deepEqual(
    lib.locationsFromUpload({ document: { location: 'b.md-2.json' } }),
    ['b.md-2.json']
  );
  assert.deepEqual(
    lib.locationsFromUpload({
      success: true,
      documents: [{ location: 'c.md-3.json' }, { title: '没有 location' }, null],
    }),
    ['c.md-3.json']
  );
  assert.deepEqual(lib.locationsFromUpload({ success: true }), []);
  assert.deepEqual(lib.locationsFromUpload(null), []);
});

test('pickProxyHeaders 丢掉 Cookie / Origin / Authorization', () => {
  const picked = lib.pickProxyHeaders({
    'content-type': 'multipart/form-data; boundary=x',
    'content-length': '123',
    'accept': 'application/json',
    cookie: 'session=secret',
    origin: 'http://evil.example',
    authorization: 'Bearer stolen',
    'x-forwarded-for': '1.2.3.4',
  });
  assert.deepEqual(picked, {
    'content-type': 'multipart/form-data; boundary=x',
    'content-length': '123',
    accept: 'application/json',
  });
});

test('resolveStaticPath 只放行根目录内的文件', () => {
  const root = path.resolve('D:', 'LLM', 'AnythingLLMWebPage');
  assert.equal(
    lib.resolveStaticPath(root, '/upload.html'),
    path.join(root, 'upload.html')
  );
  assert.equal(lib.resolveStaticPath(root, '/lib.js'), path.join(root, 'lib.js'));
  assert.equal(lib.resolveStaticPath(root, '/../server.js'), null, '不允许跳出根目录');
  assert.equal(lib.resolveStaticPath(root, '/../../Windows/win.ini'), null);
  assert.equal(lib.resolveStaticPath(root, '/'), null, '空相对路径视为越界');
});

test('errorBody 结构稳定', () => {
  assert.deepEqual(lib.errorBody('EMBED_FAILED', '向量化失败'), {
    success: false,
    code: 'EMBED_FAILED',
    error: '向量化失败',
  });
});
