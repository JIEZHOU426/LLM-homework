/**
 * 纯函数工具集：server.js 与测试共用。
 *
 * 抽出来的原因：这几件事都需要被单元测试盯着——工作区标识会拼进上游 URL、
 * 上传响应结构决定"能不能向量化"、静态文件路径决定"能不能读别处的文件"。
 */

const path = require('path');

/** AnythingLLM 的 workspace slug 白名单（会被拼进 URL，必须先校验） */
const SLUG_RE = /^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/;

function isSafeSlug(slug) {
  return typeof slug === 'string' && SLUG_RE.test(slug.trim());
}

/**
 * 从 /api/v1/document/upload 的响应里取出可向量化的文档位置。
 * AnythingLLM 的返回在不同版本里可能是 {documents:[{location}]}、
 * {document:{location}} 或 {success:true, documents:[...]}，都兼容。
 */
function locationsFromUpload(data) {
  if (!data || typeof data !== 'object') return [];
  let docs = data.documents;
  if (!Array.isArray(docs) && data.document && typeof data.document === 'object') {
    docs = [data.document];
  }
  if (!Array.isArray(docs)) return [];
  return docs
    .map((doc) => (doc && typeof doc === 'object' ? doc.location : null))
    .filter((loc) => typeof loc === 'string' && loc.trim())
    .map((loc) => loc.trim());
}

/**
 * 只保留允许转发给上游的请求头：绝不透传浏览器带来的 Cookie / Origin / Referer，
 * 也不透传客户端的 Authorization（由服务端用 API Key 覆盖）。
 */
const PASSTHROUGH_HEADERS = ['content-type', 'content-length', 'accept'];

function pickProxyHeaders(headers) {
  const picked = {};
  for (const name of PASSTHROUGH_HEADERS) {
    const value = headers && headers[name];
    if (value !== undefined) picked[name] = value;
  }
  return picked;
}

/**
 * 把 URL 路径解析为 ROOT 内的文件路径；越界（`..`、绝对盘符、同级目录前缀）
 * 一律返回 null。用 path.relative 判断而不是 startsWith 字符串比较，
 * 否则 `D:\LLM\AnythingLLMWebPage2` 会被误判为在 ROOT 内。
 */
function resolveStaticPath(root, urlPath) {
  let decoded;
  try {
    decoded = decodeURIComponent(urlPath);
  } catch (e) {
    return null; // 百分号编码不合法
  }
  const segments = decoded.split(/[/\\]+/);
  // 显式拒绝 `..` 段与盘符：normalize 会把根上的 `..` 静默吃掉，看起来"安全"
  // 其实是把请求改写成了根目录里的另一个文件，不如直接拒
  if (segments.some((seg) => seg === '..')) return null;
  if (decoded.includes(':')) return null;

  const rel = path.normalize(decoded).replace(/^([/\\])+/, '');
  if (!rel) return null;
  const target = path.resolve(root, rel);
  const relative = path.relative(root, target);
  if (!relative || relative.startsWith('..') || path.isAbsolute(relative)) return null;
  return target;
}

/** 统一错误响应体：前端可以按 code 给出不同的提示文案 */
function errorBody(code, message) {
  return { success: false, code, error: message };
}

module.exports = {
  isSafeSlug,
  locationsFromUpload,
  pickProxyHeaders,
  resolveStaticPath,
  errorBody,
};
