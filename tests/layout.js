const { chromium } = require('playwright-core');
(async () => {
  const b = await chromium.launch({ executablePath: '/root/.cache/ms-playwright/chromium-1248/chrome-linux-arm64/chrome', args: ['--no-sandbox'] });
  const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, locale: 'zh-CN' });
  const p = await ctx.newPage();
  const errs = [];
  p.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
  p.on('pageerror', e => errs.push('pageerror: ' + e.message));
  await p.goto(process.env.URL || 'http://127.0.0.1:8099/vocab.html');
  await p.waitForTimeout(300);

  const audit = async (label) => {
    const r = await p.evaluate(() => {
      const vw = document.documentElement.clientWidth;
      const issues = [];
      if (document.documentElement.scrollWidth > vw + 1) issues.push(`页面横向溢出 ${document.documentElement.scrollWidth} > ${vw}`);
      document.querySelectorAll('.pvrow .ex, .qex, .qword, .arow, .cta, .card').forEach(el => {
        const b = el.getBoundingClientRect();
        if (b.right > vw + 1) issues.push(`${el.className.split(' ')[0]} 超出右边界 ${Math.round(b.right)}`);
        if (b.left < -1) issues.push(`${el.className.split(' ')[0]} 超出左边界 ${Math.round(b.left)}`);
      });
      const qw = document.querySelector('.qword');
      if (qw && qw.scrollWidth > qw.clientWidth + 2) issues.push(`单词溢出 ${qw.scrollWidth}>${qw.clientWidth}`);
      return { vw, issues };
    });
    console.log(label, JSON.stringify(r));
  };

  await audit('home');
  await p.click('[data-act="newgroup"]'); await p.waitForTimeout(250);
  await audit('preview');
  const exVisible = await p.evaluate(() => {
    const el = document.querySelector('.pvrow .ex');
    if (!el) return 'no-ex';
    return getComputedStyle(el).display;
  });
  console.log('preview 例句初始 display =', exVisible);
  await p.click('.pvrow'); await p.waitForTimeout(200);
  console.log('展开后 display =', await p.evaluate(() => getComputedStyle(document.querySelector('.pvrow .ex')).display));
  await p.screenshot({ path: '/tmp/s3-preview-open.png', fullPage: false });
  await p.click('[data-act="startQuiz"]'); await p.waitForTimeout(250);
  await audit('quiz');
  console.log('quiz 有例句 =', await p.evaluate(() => !!document.querySelector('.qex')));
  await p.click('[data-act="peek"]'); await p.waitForTimeout(250);
  await audit('quiz-reveal');
  const ex = await p.evaluate(() => {
    const e = document.querySelector('.qex');
    if (!e) return null;
    return { text: e.innerText.trim().slice(0, 60), h: e.getBoundingClientRect().height };
  });
  console.log('例句块:', JSON.stringify(ex));
  await p.screenshot({ path: '/tmp/s5-quiz-reveal.png' });
  console.log('console errors:', errs.length ? errs : 'none');
  await b.close();
})().catch(e => { console.error('ERR', e.message); process.exit(1); });
