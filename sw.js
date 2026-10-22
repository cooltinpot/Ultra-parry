// Offline support: cache the game, refresh it in the background when online.
const CACHE = 'ultra-parry-934e38b20a';
const CORE = ['./', 'index.html', 'manifest.webmanifest', 'icons/icon-192.png', 'icons/icon-512.png', 'icons/apple-touch-icon.png', 'peerjs.min.js'];
const FONT_CSS = "https://fonts.googleapis.com/css2?family=Archivo+Black&family=Archivo:ital,wght@0,500;0,800;1,800&family=Bungee&family=Chakra+Petch:wght@500;700&display=swap";
self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(async c => {
    await c.addAll(CORE);
    // save the fonts too, so the titles keep their look offline
    try {
      const res = await fetch(FONT_CSS);
      await c.put(FONT_CSS, res.clone());
      const urls = [...(await res.text()).matchAll(/url\((https:[^)]+)\)/g)].map(m => m[1]);
      await Promise.all(urls.map(u => fetch(u).then(r => c.put(u, r))));
    } catch (err) {}
  }).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return;
  if (e.request.mode === 'navigate') {
    // opening the app: try for the newest version first, fall back to the saved copy offline
    e.respondWith(caches.open(CACHE).then(async cache => {
      try {
        const res = await Promise.race([fetch(e.request), new Promise((_, no) => setTimeout(() => no(new Error('slow')), 3000))]);
        if (res && res.ok) { cache.put('index.html', res.clone()); return res; }
        throw new Error('bad response');
      } catch (err) {
        return (await cache.match('index.html')) || (await cache.match('./')) || Response.error();
      }
    }));
    return;
  }
  e.respondWith(caches.open(CACHE).then(async cache => {
    const hit = await cache.match(e.request, { ignoreVary: true }) || await cache.match(e.request, { ignoreSearch: true, ignoreVary: true });
    const net = fetch(e.request).then(res => {
      if (res && (res.ok || res.type === 'opaque')) cache.put(e.request, res.clone());
      return res;
    }).catch(() => hit);
    return hit || net;
  }));
});
