/* 服务器接口自测：node test.js  （会自动起一个临时实例，跑完关掉） */
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const os = require('os');
const assert = require('assert');

const DATA_DIR = fs.mkdtempSync(path.join(os.tmpdir(), 'wbsrv-'));
const PORT = 8799;
const BASE = 'http://127.0.0.1:' + PORT;
const PASS = 'testpass123';
const srv = spawn(process.execPath, ['server.js'], { cwd: __dirname, env: { ...process.env, PORT: String(PORT), DATA_DIR, ADMIN_PASS: PASS, ADMIN_USER: 'teacher' }, stdio: 'ignore' });

const wait = ms => new Promise(r => setTimeout(r, ms));
async function call(p, opt = {}) {
  const r = await fetch(BASE + p, { ...opt, headers: { 'content-type': 'application/json', ...(opt.headers || {}) } });
  return { status: r.status, body: await r.json().catch(() => ({})) };
}
let passed = 0;
function ok(name, cond, extra) { if (!cond) { console.error('  ✗ ' + name, extra || ''); process.exitCode = 1; } else { passed++; console.log('  ✓ ' + name); } }

(async () => {
  await wait(1200);
  try {
    console.log('[1] 认证');
    let r = await call('/api/t/login', { method: 'POST', body: JSON.stringify({ user: 'teacher', pass: 'wrong' }) });
    ok('错误密码被拒绝', r.status === 401);
    r = await call('/api/t/login', { method: 'POST', body: JSON.stringify({ user: 'teacher', pass: PASS }) });
    ok('老师登录成功', r.status === 200 && r.body.token);
    const T = { authorization: 'Bearer ' + r.body.token };
    r = await call('/api/t/overview');
    ok('未登录看不到学生', r.status === 401);

    console.log('[2] 激活码与绑定');
    r = await call('/api/t/codes', { method: 'POST', headers: T, body: JSON.stringify({ count: 2 }) });
    const [code1, code2] = r.body.codes;
    ok('生成 2 个激活码', r.status === 200 && r.body.codes.length === 2);
    r = await call('/api/s/bind', { method: 'POST', body: JSON.stringify({ code: 'AAAA-BBBB', name: 'x' }) });
    ok('假激活码被拒绝', r.status === 404);
    r = await call('/api/s/bind', { method: 'POST', body: JSON.stringify({ code: code1, name: '小明', device: 'phone' }) });
    ok('绑定成功', r.status === 200 && r.body.token);
    const S = { authorization: 'Bearer ' + r.body.token };
    const sid = r.body.studentId;
    r = await call('/api/s/bind', { method: 'POST', body: JSON.stringify({ code: code1, name: '小红' }) });
    ok('同一激活码不能二次绑定', r.status === 409);

    console.log('[3] 上传');
    const data = { learned: 40, seq: 2, minutes: 15, today: 12, goal: 20, streak: 3, due: 4, wrongN: 2, stars: 5,
      days: { [new Date().toISOString().slice(0, 10)]: 12 },
      sessions: [{ ts: Date.now(), first: 12, total: 20, dur: 300, wrong: 2, kind: 'learn', gno: 1 }],
      groups: [
      { gno: 1, range: 0, first: 12, total: 20, wrong: [{ w: 'appear', n: 2 }, { w: 'abandon', n: 1 }] },
      { gno: 2, range: 0, first: 17, total: 20, wrong: [{ w: 'appear', n: 1 }] }
    ] };
    r = await call('/api/s/push', { method: 'POST', headers: S, body: JSON.stringify({ hash: 'h1', data }) });
    ok('第一次上传成功', r.status === 200);
    r = await call('/api/s/push', { method: 'POST', headers: S, body: JSON.stringify({ hash: 'h1', data }) });
    ok('相同数据被拒绝（409）', r.status === 409);
    r = await call('/api/s/push', { method: 'POST', body: JSON.stringify({ hash: 'h2', data }) });
    ok('没令牌不能上传', r.status === 401);
    r = await call('/api/s/push', { method: 'POST', headers: S, body: JSON.stringify({ hash: 'h2', data }) });
    ok('数据变化后可再传', r.status === 200);

    console.log('[4] 老师端数据');
    r = await call('/api/t/overview', { headers: T });
    const st = r.body.students[0];
    ok('学生出现在名单里', r.body.students.length === 1 && st.name === '小明');
    ok('统计了组数与正确率', st.summary.groups === 2 && st.summary.accuracy === 73);
    ok('错词合并计数', st.summary.topWrong[0].w === 'appear' && st.summary.topWrong[0].n === 3);
    ok('上传次数', st.pushes === 2);
    ok('今日目标与连续天数', st.summary.today === 12 && st.summary.goal === 20 && st.summary.streak === 3);
    ok('每日趋势与练习类型', Object.keys(st.summary.days).length === 1 && st.summary.kindStats.learn === 1);
    ok('班级汇总', r.body.agg.students === 1 && r.body.agg.activeToday === 1 && r.body.agg.avgAccuracy === 73);

    console.log('[5] 任务与消息');
    r = await call('/api/t/assign', { method: 'POST', headers: T, body: JSON.stringify({ title: '背第 3 组', text: '周五检查', target: 'all' }) });
    ok('发布任务', r.status === 200);
    const assignId = r.body.item.id;
    r = await call('/api/t/message', { method: 'POST', headers: T, body: JSON.stringify({ text: '记得打卡', target: sid }) });
    ok('发消息', r.status === 200);
    r = await call('/api/s/inbox', { headers: S });
    ok('学生收到 2 条', r.body.items.length === 2 && r.body.items.every(x => x.read === false));
    r = await call('/api/s/ack', { method: 'POST', headers: S, body: JSON.stringify({ id: r.body.items[0].id }) });
    ok('标记已读', r.status === 200);
    r = await call('/api/s/inbox', { headers: S });
    ok('已读状态生效', r.body.items.some(x => x.read === true));
    r = await call('/api/s/ack', { method: 'POST', headers: S, body: JSON.stringify({ id: assignId }) });
    ok('作业已读回执', r.status === 200);

    console.log('[6] 老师端反馈');
    r = await call('/api/t/note', { method: 'POST', headers: T, body: JSON.stringify({ studentId: sid, text: '重点复习 appear' }) });
    ok('保存老师备注', r.status === 200 && r.body.text.includes('appear'));
    r = await call('/api/t/student/' + sid, { headers: T });
    ok('详情带备注和回执', r.body.note.includes('appear') && r.body.assignments.some(a => a.id === assignId && a.read === true));
    r = await call('/api/t/assignments', { headers: T });
    ok('作业列表带已读统计', r.body.items[0].read === 1 && r.body.items[0].unread === 0);
    const csv = await fetch(BASE + '/api/t/export.csv', { headers: T });
    const csvText = await csv.text();
    ok('导出 CSV', csv.status === 200 && /text\/csv/.test(csv.headers.get('content-type') || '') && csvText.includes('小明') && csvText.includes('重点复习 appear'));
    r = await call('/api/t/assign/' + assignId, { method: 'DELETE', headers: T });
    ok('删除作业', r.status === 200);

    console.log('[7] 分析与安全');
    r = await call('/api/t/analyze', { method: 'POST', headers: T, body: JSON.stringify({ studentId: sid }) });
    ok('本地报告可用', r.status === 200 && r.body.text.length > 30 && r.body.source === 'local');
    r = await call('/api/t/codes', { headers: { authorization: 'Bearer bogus' } });
    ok('伪造令牌被拒绝', r.status === 401);
    const raw = await fetch(BASE + '/api/t/login', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ user: 'teacher', pass: PASS }) });
    ok('CORS 头存在', raw.headers.get('access-control-allow-origin') === '*');
    const page = await fetch(BASE + '/student.html');
    ok('学生页可访问', page.status === 200 && (await page.text()).includes('词书'));
    const admin = await fetch(BASE + '/admin');
    ok('老师页可访问', admin.status === 200 && (await admin.text()).includes('老师端'));
  } catch (e) {
    console.error('测试异常：', e); process.exitCode = 1;
  } finally {
    srv.kill();
    console.log(`\n结果：${passed} 通过${process.exitCode ? '，有失败' : '，0 失败'}`);
    setTimeout(() => process.exit(process.exitCode || 0), 200);
  }
})();
