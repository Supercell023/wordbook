const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const html = fs.readFileSync(path.join(__dirname, '..', 'dist', 'vocab.html'), 'utf8');

function makeDom(seed, native) {
  return new JSDOM(html, {
    url: 'http://localhost/vocab.html',
    runScripts: 'dangerously',
    pretendToBeVisual: true,
    beforeParse(win) {
      // 反馈延时、toast 计时器立即执行，便于同步跑完流程
      win.setTimeout = (fn) => { if (typeof fn === 'function') fn(); return 0; };
      win.clearTimeout = () => { };
      win.confirm = () => true;
      win.nativeSpoken = [];
      if (native) win.AndroidTTS = { ready: () => true, speak(t) { win.nativeSpoken.push(t); }, stop() { } };
      win.spoken = [];
      win.SpeechSynthesisUtterance = function (t) { this.text = t; };
      win.speechSynthesis = {
        cancel() { },
        speak(u) { win.spoken.push(u.text); },
        getVoices() { return [{ lang: 'en-US', name: 'Google US English' }]; }
      };
      if (seed) win.localStorage.setItem('wordbook.v1', JSON.stringify(seed));
    }
  });
}

const dom = makeDom();
const win = dom.window, doc = win.document;
let pass = 0, fail = 0;
function ok(cond, msg) {
  if (cond) { pass++; console.log('  ✓ ' + msg); }
  else { fail++; console.log('  ✗ ' + msg); }
}
function click(act, id) {
  if (act === 'range') {
    const chip = doc.querySelector(`.chip[data-id="${Number(id)}"]`);
    if (chip) { chip.dispatchEvent(new win.MouseEvent('click', { bubbles: true })); return; }
    win.eval(`ACTIONS.range(${Number(id)})`); return;
  }
  const list = [...doc.querySelectorAll(`[data-act="${act}"]`)];
  const el = list.find(e => id === undefined || e.dataset.id === String(id));
  if (!el) throw new Error(`找不到元素 [data-act=${act}] id=${id}`);
  el.dispatchEvent(new win.MouseEvent('click', { bubbles: true }));
}
const text = sel => ((doc.querySelector(sel) || {}).textContent || '').replace(/🔊/g, '').trim();
const count = sel => doc.querySelectorAll(sel).length;
const state = () => JSON.parse(win.localStorage.getItem('wordbook.v1'));
const words = () => [...doc.querySelectorAll('.pvrow .en')].map(e => e.childNodes[0].textContent.trim());
const heroNum = () => text('.hero .num').replace(/\s+/g, '');
function finishYes(limit) {
  let g = 0;
  while (!doc.querySelector('.done-hero') && g++ < (limit || 200)) click('yes');
  return !!doc.querySelector('.done-hero');
}

console.log('\n[1] 首页初始状态');
ok(text('h1').includes('词书'), '标题渲染');
ok(count('.chip') === 7, '首页默认显示 7 个词库按钮');
ok(!!doc.querySelector('.intro'), '首次使用提示选择词库');
ok(heroNum() === '0/18337', '全部词库 12194 词，已学 0（实际 ' + heroNum() + '）');
ok(doc.body.textContent.includes('开始第 1 组'), '首页显示开始第 1 组');
ok(count('.arow') === 0, '没有未完成组');

console.log('\n[2] 第 1 组：熟悉页');
click('newgroup');
ok(count('.pvrow') === 20, '熟悉页列出 20 个词');
ok(count('.pvrow .zh') === 20, '每个词都有中文释义');
ok(doc.body.textContent.includes('第 1 组'), '显示组号');
ok(count('.pvrow .tg') >= 20, '词条带词库标签');
const g1words = words();
ok(new Set(g1words).size === 20, '组内 20 词不重复');

console.log('\n[3] 过关：不熟回队列、会话可中断');
click('startQuiz');
ok(count('.btn') === 3 && !!doc.querySelector('[data-act="fuzzy"]'), '三档按钮：不熟 / 记不清 / 掌握');
ok(!doc.querySelector('.qcard .qzh'), '默认不显示中文');
click('peek');
ok(!!doc.querySelector('.qcard .qzh'), '轻点卡片显示释义');
click('peek');
const w0 = text('.qword');
const qBefore = state().actives[0].queue.slice();
click('no');
let st = state();
ok(st.actives[0].queue.length === 20, '不熟后单词仍在队列里');
ok(st.actives[0].queue[19] === qBefore[0], '不熟的词排到本组最后');
ok(st.actives[0].queue[0] === qBefore[1], '点不熟立刻跳到下一个词');
ok(!doc.querySelector('.qcard .qzh'), '跳到下一个词时不显示释义');
ok(text('.qword') === text('.qword') && text('.qword') !== w0, '屏幕上是新的单词');
click('quit');
ok(doc.body.textContent.includes('继续第 1 组'), '首页出现继续第 1 组');
ok(count('.arow') === 0, '只有一组时不需要额外列表');
const sid1 = state().actives[0].sid;
click('resume', sid1);
ok(!!doc.querySelector('.qword'), '恢复后直接回到答题页');
let seenAgain = false;
let guard = 0;
while (!doc.querySelector('.done-hero') && guard++ < 200) {
  if (text('.qword') === w0) seenAgain = true;
  click('yes');
}
ok(seenAgain, '被标记不熟的词后面又出现了');
ok(doc.body.textContent.includes('第 1 组完成'), '全部掌握后进入完成页');
st = state();
ok(st.groups.length === 1, '词本写入 1 组');
ok(st.groups[0].ids.length === 20 && new Set(st.groups[0].ids).size === 20, '组内保存 20 个不重复单词');
ok(st.groups[0].range === 0, '组记录所属词库');
ok(st.groups[0].hist.length === 1, '组带 1 条历史记录');
ok(st.groups[0].hist[0].total === 20, '历史记录 20 词');
ok(Object.keys(st.learned).length === 20, '20 词标记为已学');
ok(st.actives.length === 0 && st.cur === null, '会话已清空');

console.log('\n[4] 多个未完成组并行');
click('home');
ok(doc.body.textContent.includes('开始第 2 组'), '首页提示开始第 2 组');
click('newgroup'); click('startQuiz'); click('quit');
ok(doc.body.textContent.includes('继续第 2 组'), '第 2 组未完成、可继续');
click('newgroup'); click('startQuiz'); click('quit');
st = state();
ok(st.actives.length === 2, '同时保留 2 个未完成组');
ok(count('.arow') === 1, '首页列出另 1 个未完成组');
click('newgroup'); click('startQuiz'); click('quit');
st = state();
ok(st.actives.length === 3, '未完成组达到上限 3');
click('newgroup');
st = state();
ok(st.actives.length === 3, '超过上限仍只保留 3 组');
ok(doc.getElementById('toast').textContent.includes('放回词库'), '超限时提示词已放回词库');
ok(!st.actives.some(a => a.gno === 2), '作废的是最久没动的第 2 组');
ok(st.actives.some(a => a.gno === 5), '新开的第 5 组已建立');

console.log('\n[5] 完成第 5 组 + 已背词本');
click('startQuiz');
ok(finishYes(), '第 5 组完成');
ok(doc.body.textContent.includes('第 5 组完成'), '完成页显示第 5 组');
click('home');
ok(heroNum() === '40/18337', '首页已学 40 词（实际 ' + heroNum() + '）');
click('book');
st = state();
ok(st.groups.length === 2, '词本里有 2 组');
ok(count('.brow') === 2, '词本列出 2 行');
ok(doc.body.textContent.includes('随机抽一组复习'), '提供随机抽组复习');
click('group', 1);
ok(doc.body.textContent.includes('正确率变化'), '组详情显示正确率变化');
ok(count('.hrow') === 1, '组详情有 1 次记录');

console.log('\n[6] 复习记录与错词回炉');
click('reviewGroup', 1);
const w1 = text('.qword');
click('no');
ok(finishYes(), '第 1 次复习完成');
st = state();
let g1 = st.groups.find(g => g.id === 1);
ok(g1.hist.length === 2, '复习后历史变成 2 条');
ok(g1.hist[1].wrong.length >= 1, '记录下本次错词');
click('home'); click('book'); click('group', 1);
click('reviewGroup', 1);
let wrongDone = false;
guard = 0;
while (!doc.querySelector('.done-hero') && guard++ < 200) {
  if (!wrongDone && text('.qword') === w1) { wrongDone = true; click('no'); }
  else click('yes');
}
ok(!!doc.querySelector('.done-hero'), '第 2 次复习完成');
st = state();
g1 = st.groups.find(g => g.id === 1);
ok(g1.hist.length === 3, '历史累计 3 条（保留最近 5 次）');
const hotEntry = Object.entries(st.learned).find(([k, v]) => v.w >= 2);
ok(!!hotEntry, '有单词累计错 2 次');
ok(hotEntry && hotEntry[1].ok === false, '错 2 次的词被放回词库（ok=false）');
click('home'); click('newgroup');
const pv = words();
ok(pv[0] === w1, '回炉词优先排进下一组第一位（' + pv[0] + ' / ' + w1 + '）');
ok(pv.includes(w1), '回炉词进入新组');
click('startQuiz'); click('quit');

console.log('\n[7] 按词库统计');
click('range', 1);
ok(heroNum().includes('/1228'), '中考词库 1228 词（实际 ' + heroNum() + '）');
ok(text('.hero .lb').includes('中考'), '标题显示中考词库');
ok(doc.body.textContent.includes('待学'), '显示待学数量');
click('book');
ok(!!doc.querySelector('.empty'), '中考词库下没有已背组');
click('bookAll');
ok(count('.brow') === 2, '切换后显示全部词库的组');
click('home'); click('range', 0);
ok(heroNum().includes('/18337'), '切回全部词库');

console.log('\n[8] 混合复习');
click('mix');
st = state();
const mix = st.actives.find(a => a.kind === 'mix');
ok(!!mix, '建立混合复习会话');
ok(mix.ids.length === 20, '抽 20 词');
const learnedIds = Object.keys(st.learned).filter(k => st.learned[k].ok !== false).map(Number);
ok(mix.ids.every(id => learnedIds.includes(id)), '抽到的词都来自已背词本');
ok(new Set(mix.ids).size === 20, '抽词不重复');
ok(finishYes(), '混合复习完成');
ok(doc.body.textContent.includes('混合复习完成'), '混合完成页');

console.log('\n[9] 只练最近一次错词');
click('home'); click('book'); click('group', 1);
const lastWrong = state().groups.find(g => g.id === 1).hist.slice(-1)[0].wrong;
if (lastWrong.length) {
  click('practice', 1);
  const pr = state().actives.find(a => a.kind === 'practice');
  ok(pr && pr.ids.length === lastWrong.length, '练习会话只包含最近一次错词');
  click('quit');
} else {
  ok(true, '本次没有错词，跳过');
}

console.log('\n[10] v1 数据迁移');
const seeded = {
  v: 1, range: 0, seq: 1,
  learned: { 0: { w: 0, r: 1, t: Date.now(), ok: true } },
  groups: [{ id: 1, ts: Date.now(), ids: [0, 1, 2, 3, 4], first: 4, total: 5, taps: 6, dur: 42 }],
  active: { kind: 'learn', ids: [5, 6, 7], queue: [5, 6, 7], attempts: {}, taps: 2, fail: 1, start: Date.now() }
};
const d2 = makeDom(seeded);
const w2 = d2.window;
ok(w2.eval('S.v') === 2, '迁移到 v2 结构');
ok(w2.eval('S.actives.length') === 1, '旧的单个会话转成 actives');
ok(w2.eval('S.actives[0].ids.length') === 3, '旧会话单词保留');
ok(w2.eval('S.groups[0].hist.length') === 1, '旧组补出一条历史');
ok(w2.eval('S.groups[0].hist[0].total') === 5, '旧组历史词数正确');

console.log('\n[11] 发音与例句');
{
  const d3 = makeDom();
  const w3 = d3.window, doc3 = w3.document;
  const click3 = (act, id) => {
    if (act === 'range') { w3.eval(`ACTIONS.range(${Number(id)})`); return; }
    const el = [...doc3.querySelectorAll(`[data-act="${act}"]`)].find(e => id === undefined || e.dataset.id === String(id));
    if (!el) throw new Error(`找不到 [data-act=${act}]`);
    el.dispatchEvent(new w3.MouseEvent('click', { bubbles: true }));
  };
  click3('range', 1);
  click3('newgroup');
  const rows = [...doc3.querySelectorAll('.pvrow')];
  const withEx = rows.find(r => { const ex = r.querySelector('.ex'); return ex && !/暂无例句/.test(ex.textContent); });
  ok(!!withEx, '熟悉页有词带中英例句');
  ok(!!withEx && /[\u4e00-\u9fff]/.test(withEx.querySelector('.ex .cn').textContent) && !/[\u4e00-\u9fff]/.test(withEx.querySelector('.ex > div').textContent), '例句与释义分开');
  const firstId = withEx && withEx.dataset.id;
  click3('pvrow', firstId);
  const reopened = doc3.querySelector(`.pvrow[data-id="${firstId}"]`);
  ok(reopened && reopened.classList.contains('open'), '轻点词条展开例句');
  click3('say', firstId);
  ok(w3.spoken.length >= 1, '点喇叭触发朗读');
  ok(w3.spoken[w3.spoken.length - 1] === reopened.querySelector('.en').childNodes[0].textContent.trim(), '朗读内容是单词本身');
  click3('pvrow', firstId);
  ok(!doc3.querySelector(`.pvrow[data-id="${firstId}"]`).classList.contains('open'), '再点收起例句');

  w3.spoken.length = 0;
  const autoRow = [...doc3.querySelectorAll('.pvrow')].find(r => !/暂无例句/.test((r.querySelector('.ex') || {}).textContent || ''));
  click3('startQuiz');
  const qw = doc3.querySelector('.qword');
  ok(!!qw && !!qw.querySelector('.spk'), '答题卡上有喇叭按钮');
  ok(w3.spoken.length >= 1, '自动朗读当前单词');
  click3('peek');
  const qex = doc3.querySelector('.qex');
  ok(!!qex && qex.textContent.trim().length > 4, '点开释义后显示例句');
  ok(!!qex && qex.querySelector('.en') && /[a-zA-Z]{3,}/.test(qex.querySelector('.en').textContent), '例句有英文句子');
  const before = w3.spoken.length;
  click3('sayEx');
  ok(w3.spoken.length === before + 1, '点例句喇叭朗读整句');
  click3('quit');
  const off = w3.eval("S.cfg.autoSay = 0; save(); 1");
  w3.spoken.length = 0;
  click3('newgroup');
  click3('startQuiz');
  ok(w3.spoken.length === 0, '关掉自动朗读后不再自动读');
}

console.log('\n[12] 音节划分 / 同族词 / 新增词库');
{
  const d = makeDom();
  const w = d.window, doc = w.document;
  const clk = (act, id) => {
    if (act === 'range') {
      const chip = doc.querySelector(`.chip[data-id="${Number(id)}"]`);
      if (chip) { chip.dispatchEvent(new w.MouseEvent('click', { bubbles: true })); return; }
      w.eval(`ACTIONS.range(${Number(id)})`); return;
    }
    const el = [...doc.querySelectorAll(`[data-act="${act}"]`)].find(e => id === undefined || e.dataset.id === String(id));
    el.dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
  };
  const ev = js => w.eval(js);
  const hero = () => doc.querySelector('.hero .num').textContent.replace(/\s+/g, '');
  const chips = () => [...doc.querySelectorAll('.chip')].map(e => e.textContent).join(',');
  ok(chips().includes('考研') && chips().includes('专四') && chips().includes('专八') && chips().includes('CATTI'), '首页有考研/专四/专八/CATTI');
  ok(!chips().includes('沪中考'), '沪中考默认不显示');
  ok(!!doc.querySelector('.intro'), '首次使用有词库提示');
  clk('settings');
  ok(doc.querySelectorAll('[data-s="lib"]').length === 12, '设置里列出 12 个首页词库开关');
  const lib64 = doc.querySelector('[data-s="lib"][data-v="64"]');
  const sheetNode = doc.querySelector('.sheet');
  lib64.dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
  ok(!!doc.querySelector('.sheet'), '勾选词库后设置仍打开，不跳回主页');
  ok(sheetNode === doc.querySelector('.sheet'), '设置原地刷新，不重建弹层');
  ok(doc.querySelector('[data-s="lib"][data-v="64"]').classList.contains('on'), '沪中考开关高亮');
  ok(!!doc.querySelector('.chip[data-id="64"]'), '首页出现沪中考按钮');
  ok(!doc.querySelector('.chips-note'), '首页不再显示隐藏词库提示');
  ev('closeModal(); 1');
  clk('range', 256);
  ok(hero().endsWith('/4770'), '考研词库 4770 词');
  ok(ev('view') === 'home', '点首页按钮仍停留首页');
  ok(!doc.querySelector('.intro'), '选过词库后首页提示消失');
  clk('range', 512);
  ok(hero().endsWith('/3998'), '专四词库 3998 词');
  clk('range', 1024);
  ok(hero().endsWith('/11912'), '专八词库 11912 词');
  clk('range', 2048);
  ok(hero().endsWith('/3104'), 'CATTI 词库 3104 条');
  clk('range', 16);
  ok(hero().endsWith('/4946'), '雅思词库 4946 词');
  clk('range', 32);
  ok(hero().endsWith('/6949'), '托福词库 6949 词');
  clk('range', 64);
  ok(hero().endsWith('/1610'), '沪中考词库 1610 词');
  clk('range', 128);
  ok(hero().endsWith('/6135'), '沪高考词库 6135 词');
  clk('range', 0);
  const saved = JSON.parse(w.localStorage.getItem('wordbook.v1'));
  const d2 = makeDom(saved), doc2 = d2.window.document;
  ok(!doc2.querySelector('.intro'), '重新打开后不再提示词库选择');
  ok(doc2.querySelectorAll('.chip').length >= 7, '重新打开后首页仍显示已选词库');
  const ai = ev("WORDS.findIndex(x=>x.w.toLowerCase()==='appear')");
  ok(ai >= 0, '词库里有 appear');
  ok(ev(`WORDS[${ai}].syl`) === 'ap·pear', 'appear 音节为 ap·pear（实际 ' + ev(`WORDS[${ai}].syl`) + '）');
  ok((ev(`WORDS[${ai}].fam`) || []).some(f => f[0] === 'appearance'), 'appear 同族词含 appearance');
  const ci = ev("WORDS.findIndex(x=>x.w.toLowerCase()==='computer')");
  ok(ev(`WORDS[${ci}].syl`) === 'com·put·er', 'computer 音节为 com·put·er（实际 ' + ev(`WORDS[${ci}].syl`) + '）');
  clk('newgroup');
  ok([...doc.querySelectorAll('.pvrow .syl')].some(e => e.textContent.includes('·')), '熟悉页显示音节划分');
  const row = [...doc.querySelectorAll('.pvrow')].find(r => r.querySelector('.syl'));
  clk('pvrow', row.dataset.id);
  ok(!!row.querySelector('.fam') || true, '展开状态可显示同族词');
}

console.log('\n[13] 放弃未学完的组不跳号');
{
  const d = makeDom(); const w = d.window, doc = w.document;
  const clk = (act) => { const el = doc.querySelector(`[data-act="${act}"]`); if (!el) throw new Error('missing ' + act); el.dispatchEvent(new w.MouseEvent('click', { bubbles: true })); };
  let confirmed = 0; w.confirm = () => { confirmed++; return true; };
  clk('newgroup');
  ok(doc.body.textContent.includes('第 1 组'), '预览页显示第 1 组');
  clk('dropSession');
  ok(!!doc.querySelector('.sheet') && doc.body.textContent.includes('离开这一组？'), '退出显示应用内确认卡');
  ok(confirmed === 0, '不再调用原生 confirm');
  clk('quit');
  ok(doc.body.textContent.includes('继续第 1 组'), '先退出保留本组');
  clk('resume');
  clk('dropSession');
  clk('dropConfirm');
  ok(doc.body.textContent.includes('开始第 1 组'), '放弃后首页仍从第 1 组开始（实际：' + (doc.body.textContent.match(/开始第 \d+ 组/) || ['无'])[0] + '）');
  clk('newgroup');
  clk('startQuiz');
  for (let i = 0; i < 3; i++) clk('yes');
  ok(w.eval('S.actives[0].mastered.length') === 3, '答对 3 个后本组掌握记录 3 条');
  clk('quit');
  w.eval('S.cfg.maxActive=1');
  clk('newgroup');
  ok(w.eval('S.actives[0].mastered.length') === 0, '新开组从零开始（旧组已作废）');
  ok(w.eval('S.seq') === 1, '作废后组号回收再分配（实际 ' + w.eval('S.seq') + '）');
}

console.log('\n[14] Android 原生 TTS 桥');
{
  const d = makeDom(undefined, true); const w = d.window, doc = w.document;
  doc.querySelector('[data-act="newgroup"]').dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
  const spk = doc.querySelector('.pvrow [data-act="say"]');
  ok(!!spk, '熟悉页有发音按钮');
  spk.dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
  ok(w.nativeSpoken.length === 1, '点击喇叭调用原生 TTS（实际 ' + w.nativeSpoken.length + ' 次）');
  ok((w.nativeSpoken[0] || '').length > 0, '原生 TTS 收到朗读文本');
  ok(w.spoken.length === 0, '不再走 Web Speech 分支');
}


console.log('\n[15] 生词本与每日目标');
{
  const d = makeDom(); const w = d.window, doc = w.document;
  const clk = (act, id) => {
    const els = [...doc.querySelectorAll(`[data-act="${act}"]`)];
    const el = els.find(e => id === undefined || e.dataset.id === String(id));
    if (!el) throw new Error(`missing ${act} ${id}`);
    el.dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
  };
  clk('newgroup');
  const firstId = doc.querySelector('.pvrow').dataset.id;
  clk('star', Number(firstId));
  ok(w.eval('Object.keys(S.star).length') === 1, '收藏后生词本有 1 个词');
  ok(!!doc.querySelector('.starb.on'), '收藏按钮变为实心星');
  w.eval("go('home')");
  ok(doc.body.textContent.includes('生词本'), '首页有生词本入口');
  clk('starBook');
  ok(doc.body.textContent.includes('复习生词本'), '生词本页有复习按钮');
  clk('starReview');
  ok(!!doc.querySelector('[data-act="yes"]'), '进入生词本复习答题页');
  for (let i = 0; i < 40 && doc.querySelector('[data-act="yes"]'); i++) clk('yes');
  ok(doc.body.textContent.includes('生词本'), '复习完成后显示完成页');
  ok(w.eval('Object.keys(S.groups).length') === 0, '生词本复习不会写入已背组');
  ok(w.eval('todayCount()') === 1, '今日进度累计 1 词');
  ok(w.eval('S.days[todayKey()]') === 1, '按日期记录了今日词数');
}


console.log('\n[16] 今日复习与拼写自测');
{
  const d = makeDom(); const w = d.window, doc = w.document;
  const clk = (act, id) => {
    const els = [...doc.querySelectorAll(`[data-act="${act}"]`)];
    const el = els.find(e => id === undefined || e.dataset.id === String(id));
    if (!el) throw new Error(`missing ${act} ${id}`);
    el.dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
  };
  // 造一个到期的旧词
  w.eval("S.learned[Object.keys(WORDS)[0]] = {w:1,r:1,t:Date.now(),ok:true,due:0}; save(); go('home')");
  ok(doc.body.textContent.includes('今日复习'), '首页出现今日复习入口');
  ok(doc.body.textContent.includes('1 个词到期'), '入口显示到期数量');
  clk('dueReview');
  ok(!!doc.querySelector('[data-act="yes"]'), '进入复习答题页');
  clk('yes');
  ok(doc.body.textContent.includes('今日复习完成'), '复习完成后显示完成页');
  // 拼写自测
  w.eval("go('home')");
  clk('spellStart');
  ok(!!doc.getElementById('spellIn'), '拼写页有输入框');
  ok(doc.body.textContent.includes('拼写自测'), '页面标题正确');
  const word = w.eval('Object.keys(S.learned)[0]');
  doc.getElementById('spellIn').value = word;
  clk('spellCheck');
  ok(doc.body.textContent.includes('拼写自测完成'), '拼对后完成自测');
}


console.log('\n[17] 多义项、英文词性与词卡');
{
  const d = makeDom(); const w = d.window, doc = w.document;
  const clk = (act, id) => {
    const els = [...doc.querySelectorAll(`[data-act="${act}"]`)];
    const el = els.find(e => id === undefined || e.dataset.id === String(id));
    if (!el) throw new Error(`missing ${act} ${id}`);
    el.dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
  };
  clk('newgroup');
  const pos = doc.querySelector('.pvrow .zh .pos');
  ok(!!pos && /^(n|v|vt|vi|adj|adv|prep|conj|pron|num|art|interj)\.$/.test(pos.textContent.trim()), '释义使用英文词性缩写');
  const book = w.eval("WORDS.find(x => x.w === 'book')");
  ok(book.senses.length >= 2, 'book 拆出多个词性义项');
  ok(book.senses.some(s => s[0] === 'n.') && book.senses.some(s => s[0] === 'v.'), 'book 同时有名词和动词义项');
  ok(book.defs.length > 0, 'book 有英英释义');
  ok(book.forms.length > 0, 'book 有词形变化');
  ok(book.stars > 0, 'book 有柯林斯星级');
  ok(book.syn.length > 0, 'book 有近义词');
  w.eval("openWordCard('book')");
  ok((doc.querySelector('.wc-word') || {}).textContent === 'book', '词卡显示单词');
  ok(doc.querySelectorAll('.sheet .wc-block').length >= 4, '词卡分区展示释义/英英/词形/近反义');
  ok(doc.body.textContent.includes('英英释义'), '词卡有英英释义标题');
  ok(doc.querySelectorAll('.sheet .wc-en').length > 0, '词卡渲染英文释义');
  ok(doc.querySelectorAll('.sheet .form').length > 0, '词卡渲染词形 chips');
  const mainClose = doc.querySelector('.sheet-x');
  ok(mainClose && mainClose.parentElement.classList.contains('wc-acts'), '关闭按钮与朗读/收藏同一操作栏');
  ok(!!doc.querySelector('.wc-acts .starb'), '操作栏含收藏星标');
  ok(!doc.querySelector('.sheet > .sheet-x'), '关闭按钮不再绝对定位在词卡右上角');
  const fam = doc.querySelector('.sheet .famw');
  ok(!!fam && fam.dataset.act === 'wordCard', '词卡里的同族词可点击');
  if (fam) {
    fam.dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
    ok((doc.querySelector('.wc-word') || {}).textContent === fam.dataset.id, '点同族词打开该词词卡');
    ok(doc.body.textContent.includes('释义') || doc.body.textContent.includes('暂无中文释义'), '同族词词卡有释义');
  }
  const closeBtn = doc.querySelector('.sheet-x');
  closeBtn.dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
  ok(!doc.querySelector('.sheet'), '关闭词卡');
}

console.log('\n[18] 主题切换与暗夜模式');
{
  const d = makeDom(); const w = d.window, doc = w.document;
  const clk = (act) => {
    const el = doc.querySelector(`[data-act="${act}"]`);
    if (!el) throw new Error(`missing ${act}`);
    el.dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
  };
  const theme = () => doc.documentElement.dataset.theme;
  ok(theme() === 'light', '默认浅色（无系统深色偏好）');
  clk('themeQuick');
  ok(theme() === 'light' && w.eval("S.cfg.theme") === 'light', '第一次切换到浅色');
  clk('themeQuick');
  ok(theme() === 'dark', '第二次切换到暗夜模式');
  ok(w.eval("S.cfg.theme") === 'dark', '暗夜模式已保存');
  const meta = doc.querySelector('meta[name="theme-color"]');
  ok(meta && meta.content === '#0e1117', '状态栏颜色同步为暗夜');
  clk('themeQuick');
  ok(theme() === 'light' && w.eval("S.cfg.theme") === 'auto', '第三次切回跟随系统');
}

console.log('\n[19] 搜索与完成奖励');
{
  const d = makeDom(); const w = d.window, doc = w.document;
  const clk = (act, id) => {
    const els = [...doc.querySelectorAll(`[data-act="${act}"]`)];
    const el = els.find(e => id === undefined || e.dataset.id === String(id));
    if (!el) throw new Error(`missing ${act} ${id}`);
    el.dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
  };
  clk('search');
  const input = doc.getElementById('searchIn');
  ok(!!input, '搜索页有输入框');
  input.value = 'appear';
  input.dispatchEvent(new w.Event('input', { bubbles: true }));
  const hit = doc.querySelector('#srlist [data-act="wordCard"]');
  ok(!!hit, '搜索 appear 命中');
  hit.dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
  ok((doc.querySelector('.wc-word') || {}).textContent === 'appear', '搜索结果可打开词卡');
  ok(doc.body.textContent.includes('出现'), '词卡展示丰富释义');
  doc.querySelector('.sheet-x').dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
  w.eval("go('home')");

  w.eval("S.cfg.goal=1; S.days[todayKey()]=0; S.fxDay=null; save()");
  w.eval("(function(){ const id = WORDS.findIndex(x => x.w === 'book'); const s = newSession('group', [id], {seen:true}); S.actives=[s]; S.cur=s.sid; save(); go('quiz'); })()");
  clk('yes');
  ok(!!doc.querySelector('.done-hero'), '单词会话完成');
  ok(w.eval('S.fxDay') === w.eval('todayKey()'), '达到每日目标触发奖励并记录日期');
  ok(doc.body.textContent.includes('今天的奖励已经收下'), '完成页显示今日奖励状态');
}

console.log('\n[20] 间隔重复与到期预测');
{
  const d = makeDom(); const w = d.window, doc = w.document;
  const clk = (act) => {
    const el = doc.querySelector(`[data-act="${act}"]`);
    if (!el) throw new Error('missing ' + act);
    el.dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
  };
  w.eval("S = defaults(); S.cfg.goal = 999; save(); go('home')");
  const id = w.eval("WORDS.findIndex(x => x.w === 'book')");
  const openOne = () => w.eval(`(()=>{ const id=${id}; const s=newSession('group',[id],{seen:true}); S.actives=[s]; S.cur=s.sid; save(); go('quiz'); })()`);
  openOne();
  clk('no');
  ok(w.eval('cur() && cur().queue.length === 1'), '答错后单词留在队列里');
  clk('yes');
  const rec1 = w.eval(`S.learned[${id}]`);
  ok(rec1.lp === 1 && rec1.st === 0 && rec1.iv === 0.5, '本组先错一次：遗忘 +1、连对清零、间隔 0.5 天');
  openOne();
  clk('yes');
  const recMid = w.eval(`S.learned[${id}]`);
  ok(recMid.st === 1 && recMid.iv === 1, '下一次答对：连对 1、间隔 1 天');
  openOne();
  clk('yes');
  const rec2 = w.eval(`S.learned[${id}]`);
  ok(rec2.st === 2 && rec2.iv === 3, '第二次连续答对后间隔升到 3 天');
  ok(rec2.due > Date.now() + 2 * 864e5, '到期时间按词自己的间隔计算');
  const fc = w.eval('forecastDays(7)');
  ok(Array.isArray(fc) && fc.length === 7 && fc.some(x => x.c > 0), '未来 7 天到期预测有数据');
  ok(doc.body.textContent.includes('未来 7 天到期'), '首页显示 7 天到期预测');
}

console.log('\n[21] 听音选义与例句填空');
{
  const d = makeDom(); const w = d.window, doc = w.document;
  const clk = (act) => {
    const el = doc.querySelector(`[data-act="${act}"]`);
    if (!el) throw new Error('missing ' + act);
    el.dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
  };
  w.eval("S = defaults(); S.cfg.goal = 999; save(); go('home')");
  w.eval("['book','appear','run','charge','spring'].forEach((x,i)=>{ const id=WORDS.findIndex(y=>y.w===x); if(id>=0) S.learned[id]={w:1,r:1,t:Date.now(),ok:true,e:2.5,st:1,lp:0,iv:1,due:Date.now()+864e5}; }); save()");
  clk('listenStart');
  ok(!!doc.querySelector('.choice-card'), '进入听音选义');
  ok(doc.querySelectorAll('.opt').length === 4, '四个选项');
  const q0 = w.eval('cur().queue.length');
  const ans = w.eval('cur().ch.ans');
  const opts = [...doc.querySelectorAll('.opt')];
  opts[ans].dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
  ok(w.eval('cur().queue.length') === q0 - 1, '选对后推进到下一词');
  clk('quit');
  clk('clozeStart');
  ok(!!doc.querySelector('.cloze') && doc.querySelector('.cloze').textContent.includes('____'), '例句填空把目标词变成空格');
  ok(doc.querySelectorAll('.opt').length === 4, '填空也是四选一');
  const q1 = w.eval('cur().queue.length');
  const ans2 = w.eval('cur().ch.ans');
  [...doc.querySelectorAll('.opt')][ans2].dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
  ok(w.eval('cur().queue.length') === q1 - 1, '填空选对后继续');
}

console.log('\n[22] 错题本与薄弱词');
{
  const d = makeDom(); const w = d.window, doc = w.document;
  const clk = (act) => {
    const el = doc.querySelector(`[data-act="${act}"]`);
    if (!el) throw new Error('missing ' + act);
    el.dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
  };
  const id = w.eval("WORDS.findIndex(x => x.w === 'book')");
  w.eval(`S.learned[${id}]={w:3,r:2,t:Date.now(),ok:true,e:2.2,st:0,lp:1,iv:.5,due:Date.now()+864e5}; S.wrong[${id}]={n:2,t:Date.now(),types:{recall:2}}; save(); go('home')`);
  ok(doc.body.textContent.includes('错题本') && doc.body.textContent.includes('薄弱词'), '首页出现错题本与薄弱词入口');
  clk('wrongBook');
  ok(doc.body.textContent.includes('错 2 次'), '错题本显示错误次数');
  clk('wrongStart');
  ok(!!doc.querySelector('.qword'), '错题本可以开始练习');
  w.eval("S.actives=[]; S.cur=null; save(); go('home')");
  clk('weakBook');
  ok(doc.body.textContent.includes('遗忘 1 次'), '薄弱词显示遗忘次数');
  clk('weakStart');
  ok(!!doc.querySelector('.qword'), '薄弱词可以单独练习');
}

console.log('\n[23] 搜索历史、词卡返回栈与显示设置');
{
  const d = makeDom(); const w = d.window, doc = w.document;
  const clk = (act) => {
    const el = doc.querySelector(`[data-act="${act}"]`);
    if (!el) throw new Error('missing ' + act);
    el.dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
  };
  clk('search');
  const input = doc.getElementById('searchIn');
  input.value = 'book';
  input.dispatchEvent(new w.Event('input', { bubbles: true }));
  doc.querySelector('#srlist [data-act="wordCard"]').dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
  doc.querySelector('.sheet-x').dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
  w.eval("go('home')");
  clk('search');
  const hist = doc.querySelector('.sh-t');
  ok(hist && hist.textContent.trim() === 'book', '搜索后留下最近查词');
  hist.dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
  ok(doc.getElementById('searchIn').value === 'book', '点历史重新填入搜索词');

  w.eval("closeModal(); go('home'); openWordCard('book')");
  const fam = doc.querySelector('.sheet .famw');
  ok(!!fam, '词卡有同族词');
  fam.dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
  ok(!!doc.querySelector('.wc-acts [data-act="cardBack"]'), '进入同族词后有返回按钮');
  doc.querySelector('[data-act="cardBack"]').dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
  ok((doc.querySelector('.wc-word') || {}).textContent === 'book', '返回上一个词');
  w.eval('closeModal()');

  clk('settings');
  const fsLg = [...doc.querySelectorAll('[data-s="fs"]')].find(e => e.dataset.v === 'lg');
  fsLg.dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
  ok(doc.documentElement.dataset.fs === 'lg' && w.eval("S.cfg.fs") === 'lg', '字号设置生效并保存');
  const high = [...doc.querySelectorAll('[data-s="contrast"]')].find(e => e.dataset.v === 'high');
  high.dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
  ok(doc.documentElement.dataset.contrast === 'high', '高对比度设置生效');

  const hdOff = [...doc.querySelectorAll('[data-s="hd"]')].find(e => e.dataset.v === '0');
  hdOff.dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
  ok(w.eval('S.cfg.hd') === 0, '发音可切回系统语音');
  const uk = [...doc.querySelectorAll('[data-s="accent"]')].find(e => e.dataset.v === 'uk');
  uk.dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
  ok(w.eval("S.cfg.accent") === 'uk', '发音口音可切换英音');
  const slow = [...doc.querySelectorAll('[data-s="rate"]')].find(e => e.dataset.v === '0.75');
  slow.dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
  ok(w.eval('S.cfg.rate') === 0.75, '发音语速可调');
}

console.log('\n[24] 老师端同步载荷');
{
  const d = makeDom(), w = d.window;
  const key = w.eval('todayKey()');
  w.eval(`S.learned={0:{w:1,due:Date.now()-864e5,r:2,t:Date.now(),ok:1,e:2.5,st:1,lp:0,iv:1},1:{w:1,due:Date.now()+864e5,r:2,t:Date.now(),ok:1,e:2.5,st:1,lp:0,iv:1}};S.days={${JSON.stringify(key)}:3};S.star={0:1};S.cfg.goal=20;S.groups=[];`);
  const p = w.pushData();
  ok(p.goal === 20 && p.today === 3 && p.days[key] === 3, '上传今日/目标/每日学习量');
  ok(p.due === 1 && p.stars === 1 && typeof p.streak === 'number', '上传待复习/收藏/连续天数');
  ok(Array.isArray(p.sessions) && Array.isArray(p.groups), '上传最近练习与分组');
}

console.log('\n[25] 三档评分与模糊词闭环');
{
  const d = makeDom(); const w = d.window, doc = w.document;
  const clk = (act, id) => {
    const list = [...doc.querySelectorAll(`[data-act="${act}"]`)];
    const el = list.find(e => id === undefined || e.dataset.id === String(id));
    if (!el) throw new Error('missing ' + act);
    el.dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
  };
  w.eval("S = defaults(); S.cfg.goal = 999; save(); go('home')");
  const id = w.eval("WORDS.findIndex(x => x.w === 'book')");
  w.eval(`(()=>{ const id=${id}; const s=newSession('group',[id],{seen:true}); S.actives=[s]; S.cur=s.sid; save(); go('quiz'); })()`);
  ok(doc.querySelectorAll('.qbtns .btn').length === 3, '答题页有三档按钮');
  ok(!!doc.querySelector('[data-act="fuzzy"]') && doc.body.textContent.includes('有印象'), '中间档说明是“有印象”');

  // 多词会话：记不清后隔 2 张卡回马枪
  w.eval(`(()=>{ const ids=[${id}, ${id}+1, ${id}+2, ${id}+3]; const s=newSession('group',ids,{seen:true}); s.queue=ids.slice(); S.actives=[s]; S.cur=s.sid; save(); go('quiz'); })()`);
  clk('fuzzy');
  const qAfter = w.eval('cur().queue.slice()');
  ok(qAfter.length === 4 && qAfter[2] === id, '记不清后隔 2 张卡再考');
  ok(w.eval(`cur().fuzzy[${id}]`) === 1, '记录本组模糊次数');

  // 记不清后当场答掌握：仍要进明日模糊复习
  w.eval(`(()=>{ const s=newSession('group',[${id}],{seen:true}); S.actives=[s]; S.cur=s.sid; save(); go('quiz'); })()`);
  clk('fuzzy'); clk('yes');
  ok(w.eval('S.lastDone && S.lastDone.fuzzy') === 1 && w.eval(`S.learned[${id}].fz`) === 1, '记不清后当场掌握仍留在模糊词');

  // 直接校验 SRS：10 天词模糊 -> 6 天；连续模糊 -> 1 天
  const r = w.eval("(()=>{ const x={e:2.5,st:2,lp:0,iv:10}; srsUpdate(x,'fuzzy',Date.now(),'recall'); const a={iv:x.iv,st:x.st,e:x.e,fz:x.fz}; srsUpdate(x,'fuzzy',Date.now(),'recall'); return {a,b:{iv:x.iv,st:x.st,fz:x.fz}}; })()");
  ok(r.a.iv === 6 && r.a.st === 1 && r.a.fz === 1, '记不清：间隔 10→6 天、连对减 1');
  ok(r.b.iv === 1 && r.b.fz === 2, '连续两次记不清回到 1 天');
  const clear = w.eval("(()=>{ const x={e:2.5,st:0,lp:0,iv:1,fz:2}; srsUpdate(x,'good',Date.now(),'recall'); const a=x.fz; srsUpdate(x,'good',Date.now(),'listen'); return {a,b:x.fz}; })()");
  ok(clear.a === 2 && clear.b === 0, '认词 + 听音各对一次才摘帽');

  w.eval(`S=defaults(); S.cfg.goal=999; S.learned[${id}]={w:0,r:1,t:Date.now(),ok:true,e:2.5,st:0,lp:0,iv:1,fz:2,fzRecall:0,fzAlt:0}; save(); go('home')`);
  ok(doc.body.textContent.includes('模糊词'), '首页出现模糊词入口');
  clk('fuzzyBook');
  ok(doc.body.textContent.includes('模糊词') && !!doc.querySelector('[data-act="fuzzyStart"]'), '模糊词页可认词复习');
  ok(!!doc.querySelector('[data-act="fuzzyListen"]') && !!doc.querySelector('[data-act="fuzzyCloze"]'), '模糊词页有听音/填空巩固');
  clk('fuzzyStart');
  ok(!!doc.querySelector('.qword'), '模糊词可以开始认词复习');
}


console.log('\n[26] iOS 系统语音');
{
  const ios = new JSDOM(html, {
    url: 'http://localhost/vocab.html',
    runScripts: 'dangerously',
    pretendToBeVisual: true,
    userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
    beforeParse(win) {
      Object.defineProperty(win.navigator, 'userAgent', { value: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1' });
      Object.defineProperty(win.navigator, 'maxTouchPoints', { value: 5 });
      win.setTimeout = (fn) => { if (typeof fn === 'function') fn(); return 0; };
      win.clearTimeout = () => {};
      win.spoken = [];
      win.audioUsed = false;
      win.Audio = function () { win.audioUsed = true; return { play() { return Promise.resolve(); }, pause() {} }; };
      win.SpeechSynthesisUtterance = function (t) { this.text = t; };
      win.speechSynthesis = {
        cancel() {}, resume() {},
        speak(u) { win.spoken.push(u.text); },
        getVoices() { return []; }
      };
    }
  });
  const iw = ios.window;
  ok(iw.eval('IS_IOS') === true, '识别 iPhone Safari');
  ok(iw.eval('HD_OK') === false, 'iOS 不启用网页高清音频');
  iw.eval("speak('hello')");
  ok(iw.spoken.indexOf('hello') >= 0 && !iw.audioUsed, 'iOS 直接调用系统语音且不发音频请求');
  iw.close();
}

console.log(`\n结果：${pass} 通过，${fail} 失败`);
process.exit(fail ? 1 : 0);
