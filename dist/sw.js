/* 词书 · Service Worker
 * 目标：添加到主屏幕后可离线打开；升级时安全换版，不让旧缓存卡住新版页面。
 * 注意：sw.js 必须放在站点根目录（或带 Service-Worker-Allowed 头），本仓库由
 *       build.sh 同步到 dist / server/public / android/assets / ios/Resources/www。
 *
 * 更新流程：新 SW 安装完 skipWaiting → activate 删除旧 wordbook-* 缓存并
 * clients.claim()；若确实是从旧版本升级，向所有 window client 发
 * {type:'WB_UPDATED', version, cache}，页面据此提示「新版本，点此刷新」。
 */
const VERSION = 'v4';
const CACHE = 'wordbook-' + VERSION;

/* 预缓存清单：单个资源失败不影响安装（旧版本里 ./student.html 在静态托管下会 404，
 * 这里保留它但不再依赖它成功）。 */
const CORE = [
  './vocab.html',
  './manifest.json',
  './icons/icon.svg',
  './icons/icon-192.png',
  './icons/icon-512.png',
  './icons/maskable.svg',
  './icons/maskable-512.png',
  './icons/apple-touch-icon.png',
  './icons/favicon-32.png'
];

async function notifyUpdated() {
  let clients = [];
  try {
    clients = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
  } catch (_) { return; }
  for (const client of clients) {
    try { client.postMessage({ type: 'WB_UPDATED', version: VERSION, cache: CACHE }); } catch (_) {}
  }
}

self.addEventListener('install', event => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    await Promise.all(CORE.map(async url => {
      try {
        const res = await fetch(new Request(url, { cache: 'reload' }));
        if (res && res.ok) await cache.put(url, res);
      } catch (_) { /* 单个资源失败不影响安装 */ }
    }));
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    const hadOld = keys.some(k => k !== CACHE && k.startsWith('wordbook-'));
    await Promise.all(keys.filter(k => k !== CACHE && k.startsWith('wordbook-')).map(k => caches.delete(k)));
    if (self.registration.navigationPreload) {
      try { await self.registration.navigationPreload.disable(); } catch (_) {}
    }
    await self.clients.claim();
    /* 首次安装没有旧缓存，不打扰页面；真正的版本升级才通知。 */
    if (hadOld) await notifyUpdated();
  })());
});

/* manifest / sw 本身走网络优先，避免旧清单把新图标/新名字缓存住 */
const NETWORK_FIRST = /\/(manifest\.webmanifest|manifest\.json|sw\.js)$/;

function isCacheable(res) {
  return res && res.ok && res.status === 200 && (res.type === 'basic' || res.type === 'default');
}

self.addEventListener('fetch', event => {
  const req = event.request;
  if (req.method !== 'GET') return;

  let url;
  try { url = new URL(req.url); } catch (_) { return; }
  if (url.protocol !== 'http:' && url.protocol !== 'https:') return;
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith('/api/')) return;

  /* 页面导航：网络优先，断网回落到缓存的 vocab.html */
  if (req.mode === 'navigate') {
    event.respondWith((async () => {
      try {
        const res = await fetch(req);
        if (isCacheable(res)) {
          const copy = res.clone();
          caches.open(CACHE).then(c => c.put(req, copy)).catch(() => {});
        }
        return res;
      } catch (_) {
        const cache = await caches.open(CACHE);
        return (await cache.match(req)) ||
               (await cache.match('./vocab.html')) ||
               (await cache.match(new URL('./vocab.html', self.registration.scope).href)) ||
               new Response('离线状态，请先联网打开一次词书。', {
                 status: 503,
                 headers: { 'content-type': 'text/plain; charset=utf-8' }
               });
      }
    })());
    return;
  }

  if (NETWORK_FIRST.test(url.pathname)) {
    event.respondWith((async () => {
      try {
        const res = await fetch(req);
        if (isCacheable(res)) {
          const copy = res.clone();
          caches.open(CACHE).then(c => c.put(req, copy)).catch(() => {});
        }
        return res;
      } catch (_) {
        const hit = await caches.match(req);
        return hit || Response.error();
      }
    })());
    return;
  }

  /* 其它静态资源：缓存优先，回退网络并顺手写缓存 */
  event.respondWith((async () => {
    const hit = await caches.match(req, { ignoreSearch: false });
    if (hit) return hit;
    try {
      const res = await fetch(req);
      if (isCacheable(res)) {
        const copy = res.clone();
        caches.open(CACHE).then(c => c.put(req, copy)).catch(() => {});
      }
      return res;
    } catch (_) {
      return Response.error();
    }
  })());
});

/* 页面发 {type:'SKIP_WAITING'} 可立即接管（设置里「检查更新」用得上） */
self.addEventListener('message', event => {
  const data = event.data || {};
  if (data.type === 'SKIP_WAITING') {
    event.waitUntil(self.skipWaiting());
    return;
  }
  if (data.type === 'VERSION' && event.source) {
    event.source.postMessage({ type: 'VERSION', version: VERSION, cache: CACHE });
  }
});
