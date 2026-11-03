const { chromium } = require('playwright-core');
(async () => {
  const b = await chromium.launch({ executablePath: '/root/.cache/ms-playwright/chromium-1248/chrome-linux-arm64/chrome', args: ['--no-sandbox'] });
  const p = await b.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
  await p.goto(process.env.URL || 'http://127.0.0.1:8099/vocab.html');
  await p.waitForTimeout(300);
  await p.screenshot({ path: '/root/workspace/vocab/test/shot-home2.png' });
  // 学一个词后进入拼写页
  await p.evaluate(() => {
    const ids = Object.keys(WORDS).slice(0, 6);
    ids.forEach(id => { S.learned[id] = { w: 1, r: 1, t: Date.now(), ok: true, due: Date.now() + 864e5 }; });
    save();
  });
  await p.evaluate(() => ACTIONS.spellStart());
  await p.waitForTimeout(300);
  await p.screenshot({ path: '/root/workspace/vocab/test/shot-spell2.png' });
  const ov = await p.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
  console.log('spell overflow', ov);
  await b.close();
})();
