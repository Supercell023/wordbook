#!/usr/bin/env node
/* 单词本 · 班级中继服务器
 * 零依赖：Node >= 18（使用内置 http / crypto / fs）
 * 启动：node server.js [--port 8787]
 * 首次启动会生成 data/db.json 与 data/secret，并打印初始老师账号。
 */
const http = require('http');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const zlib = require('zlib');

const ROOT = __dirname;
const DATA = process.env.DATA_DIR || path.join(ROOT, 'data');
const DB_FILE = path.join(DATA, 'db.json');
const SECRET_FILE = path.join(DATA, 'secret');
const PUBLIC = path.join(ROOT, 'public');
const PORT = Number(process.env.PORT || (process.argv.includes('--port') ? process.argv[process.argv.indexOf('--port') + 1] : 8787));
const HOST = process.env.HOST || '0.0.0.0';

/* ---------------- 存储 ---------------- */
fs.mkdirSync(DATA, { recursive: true });
if (!fs.existsSync(SECRET_FILE)) fs.writeFileSync(SECRET_FILE, crypto.randomBytes(32).toString('hex'), { mode: 0o600 });
const SECRET = fs.readFileSync(SECRET_FILE, 'utf8').trim();

const FIRST_RUN = !fs.existsSync(DB_FILE);
const DEFAULT_PASS = process.env.ADMIN_PASS || crypto.randomBytes(4).toString('hex');
const INITIAL = {
  teacher: { user: process.env.ADMIN_USER || 'teacher', passHash: sha(DEFAULT_PASS), initPass: process.env.ADMIN_PASS ? '' : DEFAULT_PASS },
  codes: {},      // code -> {used, studentId, createdAt}
  students: {},   // id -> {id,name,token,createdAt,lastPushAt,lastHash,device}
  pushes: [],     // {id,studentId,at,hash,summary,raw}
  assignments: [],// {id,at,title,text,due,target}
  messages: [],   // {id,at,text,target}
  acks: {},       // studentId -> {itemId: at}
  notes: {},      // studentId -> 老师备注
  llm: { url: process.env.LLM_URL || 'https://api.deepseek.com/chat/completions', key: process.env.LLM_KEY || process.env.DEEPSEEK_API_KEY || '', model: process.env.LLM_MODEL || 'deepseek-chat' },
  log: []         // {at, kind, msg}
};
let DB = fs.existsSync(DB_FILE) ? JSON.parse(fs.readFileSync(DB_FILE, 'utf8')) : INITIAL;
for (const k of Object.keys(INITIAL)) if (DB[k] === undefined) DB[k] = INITIAL[k];

let writing = Promise.resolve();
function save() {
  writing = writing.then(() => new Promise(res => {
    const tmp = DB_FILE + '.tmp';
    fs.writeFile(tmp, JSON.stringify(DB, null, 1), () => fs.rename(tmp, DB_FILE, () => res()));
  }));
  return writing;
}
function sha(s) { return crypto.createHash('sha256').update(String(s)).digest('hex'); }
function now() { return Date.now(); }
function uid(n = 10) { return crypto.randomBytes(n).toString('hex').slice(0, n); }
function note(kind, msg) { DB.log.push({ at: now(), kind, msg }); if (DB.log.length > 500) DB.log.splice(0, 200); }

/* ---------------- 令牌 ---------------- */
function sign(payload) {
  const body = Buffer.from(JSON.stringify(payload)).toString('base64url');
  const mac = crypto.createHmac('sha256', SECRET).update(body).digest('base64url');
  return body + '.' + mac;
}
function verify(token, role) {
  if (!token || typeof token !== 'string' || !token.includes('.')) return null;
  const [body, mac] = token.split('.');
  const want = crypto.createHmac('sha256', SECRET).update(body).digest('base64url');
  if (mac !== want) return null;
  let p; try { p = JSON.parse(Buffer.from(body, 'base64url').toString()); } catch { return null; }
  if (p.role !== role) return null;
  if (p.exp && p.exp < now()) return null;
  return p;
}

/* ---------------- 工具 ---------------- */
const ALPHA = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
function genCode() {
  let s = '';
  for (let i = 0; i < 8; i++) s += ALPHA[crypto.randomInt(ALPHA.length)];
  return s.slice(0, 4) + '-' + s.slice(4);
}
function bad(res, code, msg) { res.writeHead(code, { 'content-type': 'application/json; charset=utf-8' }); res.end(JSON.stringify({ ok: false, error: msg })); }
function good(res, obj) { res.writeHead(200, { 'content-type': 'application/json; charset=utf-8' }); res.end(JSON.stringify({ ok: true, ...obj })); }
function readBody(req) {
  return new Promise((resolve, reject) => {
    let n = 0, chunks = [];
    req.on('data', c => { n += c.length; if (n > 512 * 1024) { reject(new Error('too large')); req.destroy(); } else chunks.push(c); });
    req.on('end', () => { try { resolve(chunks.length ? JSON.parse(Buffer.concat(chunks).toString('utf8')) : {}); } catch (e) { reject(e); } });
    req.on('error', reject);
  });
}
const bindHits = new Map();
function rateLimited(ip) {
  const t = now(), arr = (bindHits.get(ip) || []).filter(x => t - x < 60000);
  arr.push(t); bindHits.set(ip, arr);
  return arr.length > 10;
}

/* ---------------- 学生数据摘要 ---------------- */
function summarize(payload) {
  const st = payload && typeof payload === 'object' ? payload : {};
  const groups = Array.isArray(st.groups) ? st.groups : [];
  const wrongMap = {};
  let firstSum = 0, totalSum = 0, spoke = 0;
  for (const g of groups) {
    if (typeof g.first === 'number') {
      firstSum += g.first;
      totalSum += Number(g.total || 20);
    }
    for (const w of (g.wrong || [])) {
      const k = w.w || w;
      wrongMap[k] = (wrongMap[k] || 0) + (w.n || 1);
      spoke++;
    }
  }
  const topWrong = Object.entries(wrongMap).sort((a, b) => b[1] - a[1]).slice(0, 12).map(([w, n]) => ({ w, n }));

  /* 最近练习：优先用学生上报的 sessions；旧版客户端则从 groups.hist 兼容推导。 */
  const sessions = [];
  if (Array.isArray(st.sessions)) {
    for (const s of st.sessions.slice(0, 60)) {
      if (!s || typeof s !== 'object') continue;
      sessions.push({
        ts: Number(s.ts || 0), first: Number(s.first || 0), total: Math.max(1, Math.min(200, Number(s.total || 0))),
        dur: Math.max(0, Math.min(86400, Number(s.dur || 0))), wrong: Math.max(0, Number(s.wrong || 0)),
        kind: String(s.kind || '').slice(0, 16), mode: String(s.mode || '').slice(0, 16), gno: Number(s.gno || 0)
      });
    }
  } else {
    for (const g of groups) for (const h of (g.hist || [])) {
      sessions.push({
        ts: Number(h.ts || 0), first: Number(h.first || 0), total: Math.max(1, Number(h.total || g.total || 20)),
        dur: Math.max(0, Number(h.dur || 0)), wrong: Array.isArray(h.wrong) ? h.wrong.length : 0,
        kind: String(h.kind || 'learn').slice(0, 16), mode: String(h.mode || '').slice(0, 16), gno: Number(g.gno || 0)
      });
    }
  }
  sessions.sort((a, b) => b.ts - a.ts);

  const days = {};
  if (st.days && typeof st.days === 'object') {
    for (const [k, v] of Object.entries(st.days)) {
      if (!/^\d{4}-\d{2}-\d{2}$/.test(k)) continue;
      const n = Number(v || 0);
      if (n > 0) days[k] = Math.min(500, n);
    }
  }
  const activeDays = Object.keys(days).length;
  const lastStudy = Object.keys(days).sort().pop() || '';
  const kindStats = {};
  for (const s of sessions) {
    const k = s.kind || 'learn';
    kindStats[k] = (kindStats[k] || 0) + 1;
  }
  const today = Math.max(0, Number(st.today || 0));
  const goal = Math.max(1, Math.min(500, Number(st.goal || 20)));
  return {
    learned: Number(st.learned || 0),
    groups: groups.length,
    accuracy: totalSum ? Math.round(firstSum / totalSum * 100) : null,
    minutes: Number(st.minutes || 0),
    wrongCount: spoke,
    topWrong,
    groupsDetail: groups.slice(-30),
    seq: Number(st.seq || 0),
    today, goal, streak: Math.max(0, Number(st.streak || 0)),
    due: Math.max(0, Number(st.due || 0)),
    wrongN: Math.max(0, Number(st.wrongN || 0)),
    fuzzyN: Math.max(0, Number(st.fuzzyN || 0)),
    fuzzyRate: Math.max(0, Math.min(100, Number(st.fuzzyRate || 0))),
    stars: Math.max(0, Number(st.stars || 0)),
    activeDays, lastStudy, days, sessions: sessions.slice(0, 30), kindStats
  };
}

/* ---------------- 老师端汇总辅助 ---------------- */
function localDate(ts = Date.now()) {
  const d = new Date(ts);
  return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
}
function assignmentsFor(sid) {
  const ack = DB.acks[sid] || {};
  return DB.assignments.filter(a => a.target === 'all' || a.target === sid).map(a => ({
    ...a, read: !!ack[a.id], overdue: !!(a.due && a.due < localDate() && !ack[a.id])
  })).sort((a, b) => b.at - a.at);
}
function assignmentStats(sid) {
  const items = assignmentsFor(sid);
  return {
    total: items.length,
    read: items.filter(a => a.read).length,
    unread: items.filter(a => !a.read).length,
    overdue: items.filter(a => a.overdue).length
  };
}
function riskOf(student) {
  if (!student.lastPushAt) return { key: 'never', label: '未上传', level: 'muted' };
  const idle = Math.floor((Date.now() - student.lastPushAt) / 864e5);
  const sm = student.summary;
  if (idle >= 7) return { key: 'gone', label: `掉队 ${idle} 天`, level: 'bad' };
  if (idle >= 2) return { key: 'idle', label: `已 ${idle} 天未学`, level: 'warn' };
  if (sm && sm.accuracy != null && sm.accuracy < 60) return { key: 'low', label: '正确率偏低', level: 'warn' };
  if (sm && sm.due >= 30) return { key: 'due', label: '复习积压', level: 'warn' };
  if (sm && sm.today <= 0) return { key: 'today', label: '今日未学', level: 'muted' };
  return { key: 'ok', label: '状态正常', level: 'ok' };
}

function localReport(student, summary) {
  if (!summary) return '这个学生还没有上传过数据。等他上传后，这里会显示学习报告。';
  const lines = [];
  lines.push(`本班学生「${student.name}」目前已上传 ${DB.pushes.filter(p => p.studentId === student.id).length} 次学习数据。`);
  lines.push(`累计学过 ${summary.groups} 组，首次正确率平均 ${summary.accuracy == null ? '暂无' : summary.accuracy + '%'}。`);
  if (summary.topWrong.length) {
    lines.push('错得最多的词：' + summary.topWrong.map(t => `${t.w}（${t.n}次）`).join('、') + '。');
    lines.push('建议：把这些词单独组成一组，用「不熟」多过两轮，并让他在例句里复现。');
  } else {
    lines.push('暂无明显高频错词，可以适当提高新词比例或加快节奏。');
  }
  if (summary.accuracy != null && summary.accuracy < 50) lines.push('首次正确率偏低，建议每组词先看一遍中文释义再开始，或把每组降到 10 个词。');
  if (summary.accuracy != null && summary.accuracy > 85) lines.push('正确率很高，可以尝试更大词库或加速。');
  lines.push('（未配置大模型时由服务器本地规则生成；配置 LLM_KEY 后会换成 AI 点评。）');
  return lines.join('\n');
}

async function aiReport(student, summary) {
  const cfg = DB.llm;
  if (!cfg.key) return { text: localReport(student, summary), source: 'local' };
  const recent = DB.pushes.filter(p => p.studentId === student.id).slice(-8).map(p => p.summary);
  const prompt = `你是一位英语老师，请根据学生的背单词数据写一段简短的点评（150字以内），让学生知道下一步该做什么。数据如下：\n学生：${student.name}\n最近几次学习：${JSON.stringify(recent).slice(0, 4000)}\n错词排行：${JSON.stringify(summary?.topWrong || [])}\n请只输出点评正文，不要客套话。`;
  try {
    const r = await fetch(cfg.url, {
      method: 'POST',
      headers: { 'content-type': 'application/json', authorization: 'Bearer ' + cfg.key },
      body: JSON.stringify({ model: cfg.model, messages: [{ role: 'user', content: prompt }], temperature: 0.6, max_tokens: 400 }),
      signal: AbortSignal.timeout(30000)
    });
    const j = await r.json();
    const text = j?.choices?.[0]?.message?.content?.trim();
    if (!text) throw new Error((j && j.error && j.error.message) || 'empty');
    return { text, source: 'llm' };
  } catch (e) {
    note('llm-error', String(e && e.message || e));
    return { text: localReport(student, summary), source: 'local-fallback' };
  }
}

/* ---------------- 静态文件 ---------------- */
const MIME = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8', '.json': 'application/json; charset=utf-8',
  '.webmanifest': 'application/manifest+json; charset=utf-8',
  '.png': 'image/png', '.svg': 'image/svg+xml', '.ico': 'image/x-icon',
  '.apk': 'application/vnd.android.package-archive', '.txt': 'text/plain; charset=utf-8'
};
const COMPRESSIBLE = /^(?:text\/|application\/(?:json|manifest\+json|javascript)|image\/svg\+xml)/i;
const GZIP_MIN_BYTES = 1024;

/* 文本资源按 Accept-Encoding 协商 gzip；图片 / APK 等二进制原样发送。
 * Content-Length 按实际发送的字节数写，Vary 让缓存区分压缩与否。 */
function serveFile(req, res, file, download, cache) {
  fs.readFile(file, (err, buf) => {
    if (err) { res.writeHead(404, { 'content-type': 'text/plain; charset=utf-8' }); res.end('not found'); return; }
    const type = path.basename(file) === 'manifest.json'
      ? 'application/manifest+json; charset=utf-8'
      : (MIME[path.extname(file).toLowerCase()] || 'application/octet-stream');
    const h = { 'content-type': type, 'cache-control': cache || 'no-cache' };
    if (download) h['content-disposition'] = 'attachment; filename="' + path.basename(file) + '"';
    if (COMPRESSIBLE.test(type)) h['vary'] = 'accept-encoding';
    const gzip = !download && buf.length >= GZIP_MIN_BYTES && COMPRESSIBLE.test(type)
      && /\bgzip\b/i.test(String(req.headers['accept-encoding'] || ''));
    if (!gzip) { h['content-length'] = buf.length; res.writeHead(200, h); res.end(buf); return; }
    zlib.gzip(buf, { level: 6 }, (e, z) => {
      if (e) { h['content-length'] = buf.length; res.writeHead(200, h); res.end(buf); return; }
      h['content-encoding'] = 'gzip';
      h['content-length'] = z.length;
      res.writeHead(200, h); res.end(z);
    });
  });
}

/* ---------------- 路由 ---------------- */
const handler = async (req, res) => {
  res.setHeader('access-control-allow-origin', '*');
  res.setHeader('access-control-allow-headers', 'content-type, authorization');
  res.setHeader('access-control-allow-methods', 'GET, POST, DELETE, OPTIONS');
  if (req.method === 'OPTIONS') { res.writeHead(204); res.end(); return; }
  const url = new URL(req.url, 'http://x');
  const p = url.pathname;
  const ip = (req.socket.remoteAddress || '').replace('::ffff:', '');

  try {
    /* ---------- 页面 ---------- */
    if (p === '/' ) { res.writeHead(302, { location: '/vocab.html' }); res.end(); return; }
    if (p === '/admin' || p === '/admin.html') return serveFile(req, res, path.join(ROOT, 'admin.html'));
    if (p === '/student.html' || p === '/vocab.html' || p === '/index.html') return serveFile(req, res, path.join(PUBLIC, 'vocab.html'));
    if (p === '/manifest.json' || p === '/manifest.webmanifest') return serveFile(req, res, path.join(PUBLIC, 'manifest.json'));
    if (p === '/sw.js') {
      res.setHeader('service-worker-allowed', '/');
      return serveFile(req, res, path.join(PUBLIC, 'sw.js'), false, 'no-store');
    }
    if (p === '/favicon.ico' || p === '/favicon.png') return serveFile(req, res, path.join(PUBLIC, 'icons/favicon-32.png'));
    if (p === '/apple-touch-icon.png' || p === '/apple-touch-icon-precomposed.png') return serveFile(req, res, path.join(PUBLIC, 'icons/apple-touch-icon.png'));
    if (p.startsWith('/icons/') && !p.includes('..')) return serveFile(req, res, path.join(PUBLIC, p.slice(1)));
    if (p.startsWith('/apk/')) return serveFile(req, res, path.join(ROOT, 'apk', p.slice(5)), true);
    if (p.startsWith('/static/')) return serveFile(req, res, path.join(PUBLIC, p.slice(8)));
    if (p === '/api/health') {
      res.writeHead(200, { 'content-type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify({ ok: true, ts: Date.now(), students: Object.keys(DB.students).length }));
      return;
    }

    /* ---------- 学生 ---------- */
    if (p === '/api/s/bind' && req.method === 'POST') {
      if (rateLimited(ip)) return bad(res, 429, '尝试太频繁，请 1 分钟后再试');
      const b = await readBody(req);
      const code = String(b.code || '').trim().toUpperCase();
      const name = String(b.name || '').trim().slice(0, 20);
      if (!/^[A-Z0-9]{4}-[A-Z0-9]{4}$/.test(code)) return bad(res, 400, '激活码格式不对，应是 XXXX-XXXX');
      if (!name) return bad(res, 400, '请填写你的名字或昵称');
      const c = DB.codes[code];
      if (!c) return bad(res, 404, '激活码不存在，请向老师确认');
      if (c.used) return bad(res, 409, '这个激活码已经被使用了，请联系老师要一个新的');
      const id = 's_' + uid(8);
      DB.codes[code].used = true; DB.codes[code].studentId = id;
      DB.students[id] = { id, name, token: '', createdAt: now(), lastPushAt: 0, lastHash: '', device: String(b.device || '').slice(0, 80) };
      const token = sign({ role: 'student', sid: id, exp: now() + 365 * 864e5 });
      DB.students[id].token = token;
      note('bind', `${name} 用激活码 ${code} 绑定了设备`);
      await save();
      return good(res, { token, studentId: id, name });
    }

    if (p === '/api/s/me' && req.method === 'GET') {
      const t = verify((req.headers.authorization || '').replace('Bearer ', ''), 'student');
      if (!t) return bad(res, 401, '登录已失效，请重新绑定');
      const s = DB.students[t.sid];
      if (!s) return bad(res, 401, '学生不存在');
      return good(res, { id: s.id, name: s.name, lastPushAt: s.lastPushAt, pushed: DB.pushes.filter(x => x.studentId === s.id).length });
    }

    if (p === '/api/s/push' && req.method === 'POST') {
      const t = verify((req.headers.authorization || '').replace('Bearer ', ''), 'student');
      if (!t) return bad(res, 401, '登录已失效，请重新绑定');
      const s = DB.students[t.sid];
      if (!s) return bad(res, 401, '学生不存在');
      const b = await readBody(req);
      const hash = String(b.hash || '').slice(0, 80);
      if (!hash) return bad(res, 400, '缺少数据指纹');
      if (hash === s.lastHash) return bad(res, 409, '没有新的学习数据，这次不用上传');
      const summary = summarize(b.data || {});
      const push = { id: 'p_' + uid(8), studentId: s.id, at: now(), hash, summary, raw: b.data || {} };
      DB.pushes.push(push);
      if (DB.pushes.length > 5000) DB.pushes.splice(0, 1000);
      s.lastHash = hash; s.lastPushAt = push.at;
      note('push', `${s.name} 上传了学习数据（${summary.groups} 组）`);
      await save();
      return good(res, { at: push.at, id: push.id });
    }

    if (p === '/api/s/inbox' && req.method === 'GET') {
      const t = verify((req.headers.authorization || '').replace('Bearer ', ''), 'student');
      if (!t) return bad(res, 401, '登录已失效');
      const s = DB.students[t.sid];
      const ack = DB.acks[s.id] || {};
      const items = [
        ...DB.assignments.filter(x => x.target === 'all' || x.target === s.id).map(x => ({ ...x, kind: 'assign' })),
        ...DB.messages.filter(x => x.target === 'all' || x.target === s.id).map(x => ({ ...x, kind: 'msg' }))
      ].sort((a, b) => b.at - a.at).map(x => ({ ...x, read: !!ack[x.id] }));
      return good(res, { items: items.slice(0, 50) });
    }

    if (p === '/api/s/ack' && req.method === 'POST') {
      const t = verify((req.headers.authorization || '').replace('Bearer ', ''), 'student');
      if (!t) return bad(res, 401, '登录已失效');
      const b = await readBody(req);
      const ack = DB.acks[t.sid] || (DB.acks[t.sid] = {});
      if (b.id) ack[String(b.id)] = now();
      await save();
      return good(res, {});
    }

    /* ---------- 老师 ---------- */
    if (p === '/api/t/login' && req.method === 'POST') {
      if (rateLimited(ip)) return bad(res, 429, '尝试太频繁，请稍后');
      const b = await readBody(req);
      if (String(b.user || '') !== DB.teacher.user || sha(b.pass || '') !== DB.teacher.passHash) {
        note('login-fail', `老师登录失败 (${ip})`);
        await save();
        return bad(res, 401, '账号或密码不对');
      }
      const token = sign({ role: 'teacher', exp: now() + 30 * 864e5 });
      await save();
      return good(res, { token });
    }

    const T = (req) => verify((req.headers.authorization || '').replace('Bearer ', ''), 'teacher');

    if (p === '/api/t/overview' && req.method === 'GET') {
      if (!T(req)) return bad(res, 401, '请先登录');
      const students = Object.values(DB.students).map(s => {
        const ps = DB.pushes.filter(x => x.studentId === s.id);
        const last = ps[ps.length - 1];
        const row = {
          id: s.id, name: s.name, createdAt: s.createdAt, lastPushAt: s.lastPushAt, pushes: ps.length,
          device: s.device || '', summary: last ? last.summary : null,
          note: DB.notes[s.id] || '', assignments: assignmentStats(s.id)
        };
        row.risk = riskOf(row);
        row.idleDays = s.lastPushAt ? Math.floor((Date.now() - s.lastPushAt) / 864e5) : null;
        return row;
      }).sort((a, b) => (b.lastPushAt || 0) - (a.lastPushAt || 0));
      const withData = students.filter(s => s.summary);
      const accs = withData.filter(s => s.summary.accuracy != null).map(s => s.summary.accuracy);
      const agg = {
        students: students.length,
        activeToday: students.filter(s => s.summary && s.summary.today > 0).length,
        active7: students.filter(s => s.lastPushAt && Date.now() - s.lastPushAt < 7 * 864e5).length,
        atRisk: students.filter(s => ['never', 'gone', 'idle', 'low', 'due'].includes(s.risk.key)).length,
        avgAccuracy: accs.length ? Math.round(accs.reduce((a, b) => a + b, 0) / accs.length) : null,
        totalMinutes: students.reduce((a, s) => a + Number(s.summary && s.summary.minutes || 0), 0),
        totalLearned: students.reduce((a, s) => a + Number(s.summary && s.summary.learned || 0), 0),
        unread: students.reduce((a, s) => a + s.assignments.unread, 0)
      };
      return good(res, { students, agg, codes: Object.keys(DB.codes).filter(c => !DB.codes[c].used).length, assignments: DB.assignments.length });
    }

    if (p.startsWith('/api/t/student/') && req.method === 'GET') {
      if (!T(req)) return bad(res, 401, '请先登录');
      const id = p.split('/').pop();
      const s = DB.students[id];
      if (!s) return bad(res, 404, '没有这个学生');
      const ps = DB.pushes.filter(x => x.studentId === id);
      const last = ps[ps.length - 1];
      return good(res, {
        student: { id: s.id, name: s.name, lastPushAt: s.lastPushAt, createdAt: s.createdAt, device: s.device || '' },
        pushes: ps.slice(-20).reverse(),
        note: DB.notes[id] || '',
        assignments: assignmentsFor(id),
        summary: last ? last.summary : null
      });
    }

    if (p === '/api/t/assignments' && req.method === 'GET') {
      if (!T(req)) return bad(res, 401, '请先登录');
      const items = DB.assignments.slice(-40).reverse().map(a => {
        const targets = a.target === 'all' ? Object.values(DB.students) : [DB.students[a.target]].filter(Boolean);
        const read = targets.filter(s => (DB.acks[s.id] || {})[a.id]).length;
        return { ...a, targets: targets.length, read, unread: targets.length - read, overdue: !!(a.due && a.due < localDate()) };
      });
      return good(res, { items });
    }

    if (p.startsWith('/api/t/assign/') && req.method === 'DELETE') {
      if (!T(req)) return bad(res, 401, '请先登录');
      const id = p.split('/').pop();
      const before = DB.assignments.length;
      DB.assignments = DB.assignments.filter(a => a.id !== id);
      if (DB.assignments.length === before) return bad(res, 404, '任务不存在');
      note('assign-del', `删除任务 ${id}`);
      await save();
      return good(res, {});
    }

    if (p === '/api/t/codes' && req.method === 'GET') {
      if (!T(req)) return bad(res, 401, '请先登录');
      return good(res, { codes: Object.entries(DB.codes).map(([code, c]) => ({ code, used: c.used, at: c.createdAt, student: c.studentId ? (DB.students[c.studentId] || {}).name || '' : '' })) });
    }

    if (p === '/api/t/codes' && req.method === 'POST') {
      if (!T(req)) return bad(res, 401, '请先登录');
      const b = await readBody(req);
      const n = Math.max(1, Math.min(50, Number(b.count || 1)));
      const out = [];
      for (let i = 0; i < n; i++) {
        let code;
        do { code = genCode(); } while (DB.codes[code]);
        DB.codes[code] = { used: false, studentId: '', createdAt: now() };
        out.push(code);
      }
      note('codes', `生成 ${n} 个激活码`);
      await save();
      return good(res, { codes: out });
    }

    if (p === '/api/t/assign' && req.method === 'POST') {
      if (!T(req)) return bad(res, 401, '请先登录');
      const b = await readBody(req);
      const title = String(b.title || '').trim().slice(0, 60);
      const text = String(b.text || '').trim().slice(0, 500);
      if (!title && !text) return bad(res, 400, '内容不能为空');
      const item = { id: 'a_' + uid(8), at: now(), title, text, due: String(b.due || '').slice(0, 20), target: b.target === 'all' ? 'all' : String(b.target || 'all') };
      DB.assignments.push(item);
      note('assign', `布置任务：${title || text.slice(0, 20)}`);
      await save();
      return good(res, { item });
    }

    if (p === '/api/t/message' && req.method === 'POST') {
      if (!T(req)) return bad(res, 401, '请先登录');
      const b = await readBody(req);
      const text = String(b.text || '').trim().slice(0, 300);
      if (!text) return bad(res, 400, '说点什么吧');
      const item = { id: 'm_' + uid(8), at: now(), text, target: b.target === 'all' ? 'all' : String(b.target || 'all') };
      DB.messages.push(item);
      note('message', text.slice(0, 30));
      await save();
      return good(res, { item });
    }

    if (p === '/api/t/note' && req.method === 'POST') {
      if (!T(req)) return bad(res, 401, '请先登录');
      const b = await readBody(req);
      const s = DB.students[b.studentId];
      if (!s) return bad(res, 404, '没有这个学生');
      const text = String(b.text || '').trim().slice(0, 1000);
      if (text) DB.notes[s.id] = text; else delete DB.notes[s.id];
      note('note', `给 ${s.name} ${text ? '写了备注' : '清空了备注'}`);
      await save();
      return good(res, { text });
    }

    if (p === '/api/t/export.csv' && req.method === 'GET') {
      if (!T(req)) return bad(res, 401, '请先登录');
      const q = v => '"' + String(v == null ? '' : v).replace(/"/g, '""') + '"';
      const rows = [['姓名', '已学词数', '学习组数', '首次正确率', '累计分钟', '今日', '目标', '连续天数',
        '待复习', '错词数', '收藏', '活跃天数', '最近上传', '状态', '未读作业', '老师备注']];
      for (const s of Object.values(DB.students)) {
        const ps = DB.pushes.filter(x => x.studentId === s.id);
        const sm = ps.length ? ps[ps.length - 1].summary : null;
        const r = riskOf({ lastPushAt: s.lastPushAt, summary: sm });
        const as = assignmentStats(s.id);
        rows.push([s.name, sm ? sm.learned : 0, sm ? sm.groups : 0, sm && sm.accuracy != null ? sm.accuracy : '',
          sm ? sm.minutes : 0, sm ? sm.today : 0, sm ? sm.goal : '', sm ? sm.streak : 0,
          sm ? sm.due : 0, sm ? sm.wrongN : 0, sm ? sm.stars : 0, sm ? sm.activeDays : 0,
          s.lastPushAt ? new Date(s.lastPushAt).toLocaleString('zh-CN') : '未上传', r.label, as.unread, DB.notes[s.id] || '']);
      }
      const csv = '\uFEFF' + rows.map(r => r.map(q).join(',')).join('\r\n');
      res.writeHead(200, {
        'content-type': 'text/csv; charset=utf-8',
        'content-disposition': 'attachment; filename="wordbook-students.csv"',
        'cache-control': 'no-store'
      });
      res.end(csv);
      return;
    }

    if (p === '/api/t/analyze' && req.method === 'POST') {
      if (!T(req)) return bad(res, 401, '请先登录');
      const b = await readBody(req);
      const s = DB.students[b.studentId];
      if (!s) return bad(res, 404, '没有这个学生');
      const ps = DB.pushes.filter(x => x.studentId === s.id);
      const last = ps[ps.length - 1];
      const r = await aiReport(s, last ? last.summary : null);
      note('analyze', `${s.name} 的分析（${r.source}）`);
      await save();
      return good(res, { text: r.text, source: r.source });
    }

    if (p === '/api/t/log' && req.method === 'GET') {
      if (!T(req)) return bad(res, 401, '请先登录');
      return good(res, { log: DB.log.slice(-80).reverse() });
    }

    return bad(res, 404, '接口不存在');
  } catch (e) {
    note('error', String(e && e.message || e));
    if (res.headersSent) { try { res.end(); } catch (_) {} return; }
    return bad(res, 500, '服务器错误');
  }
};

/* ---------------- 启动（可选 HTTPS，装了证书才开） ---------------- */
const TLS_KEY = process.env.TLS_KEY || '';
const TLS_CERT = process.env.TLS_CERT || '';
const USE_TLS = !!(TLS_KEY && TLS_CERT);
const SCHEME = USE_TLS ? 'https' : 'http';
const server = USE_TLS
  ? require('https').createServer({ key: fs.readFileSync(TLS_KEY), cert: fs.readFileSync(TLS_CERT) }, handler)
  : http.createServer(handler);

server.listen(PORT, HOST, () => {
  console.log(`单词本服务器已启动： ${SCHEME}://${HOST}:${PORT}`);
  console.log(`  学生端： ${SCHEME}://<本机IP>:${PORT}/vocab.html`);
  console.log(`  老师端： ${SCHEME}://<本机IP>:${PORT}/admin`);
  if (!USE_TLS) {
    console.log('  提示：浏览器只在 HTTPS 或 localhost 下允许「添加到主屏幕」；');
    console.log('       局域网/公网部署请配 HTTPS（TLS_CERT/TLS_KEY，或前置 Caddy/Nginx）。');
  }
  if (DB.teacher.initPass) console.log(`  初始老师账号： ${DB.teacher.user} / ${DB.teacher.initPass}  （请登录后尽快改密码）`);
  console.log(`  数据文件： ${DB_FILE}`);
});
process.on('SIGINT', async () => { await save(); process.exit(0); });
