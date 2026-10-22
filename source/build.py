"""Build the installable home-screen app (PWA) into dist/ from index.html.

index.html is written as an Artifact body (no <html>/<head>), so this wraps it in a full
document with the app meta tags, then adds the manifest, service worker and icons.
Run: python3 build.py
"""
import hashlib, json, pathlib, re, shutil

ROOT = pathlib.Path(__file__).parent
DIST = ROOT / 'dist'
body = (ROOT / 'index.html').read_text()

# pull <title>, font links and <style> up into <head>; the rest stays in <body>
head_bits = re.findall(r'<title>.*?</title>|<link [^>]*>|<style>.*?</style>', body, re.S)
for bit in head_bits:
    body = body.replace(bit, '', 1)

page = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover">
<meta name="theme-color" content="#121212">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="ULTRA PARRY">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<link rel="manifest" href="manifest.webmanifest">
<script>window.UP_APP = true;</script>
<link rel="icon" type="image/png" sizes="192x192" href="icons/icon-192.png">
<link rel="apple-touch-icon" href="icons/apple-touch-icon.png">
{chr(10).join(head_bits)}
<style>html, body {{ margin: 0; }} body {{ font-size: 14px; }} img {{ max-width: 100%; }}</style>
</head>
<body>
{body.strip()}
<script>
if ('serviceWorker' in navigator) addEventListener('load', () => navigator.serviceWorker.register('sw.js').catch(() => {{}}));
</script>
</body>
</html>
'''

manifest = {
    'name': 'ULTRA PARRY',
    'short_name': 'ULTRA PARRY',
    'description': 'Parry the red ball. Every hit makes it faster.',
    'start_url': './',
    'scope': './',
    'display': 'fullscreen',
    'orientation': 'portrait',
    'background_color': '#ffffff',
    'theme_color': '#121212',
    'icons': [
        {'src': 'icons/icon-192.png', 'sizes': '192x192', 'type': 'image/png'},
        {'src': 'icons/icon-512.png', 'sizes': '512x512', 'type': 'image/png'},
        {'src': 'icons/icon-maskable-512.png', 'sizes': '512x512', 'type': 'image/png', 'purpose': 'maskable'},
    ],
}

version = hashlib.sha1(page.encode() + (ROOT / 'vendor' / 'peerjs.min.js').read_bytes()).hexdigest()[:10]
font_css = re.search(r'href="(https://fonts.googleapis.com/css2[^"]+)"', page).group(1).replace('&amp;', '&')
sw = f'''// Offline support: cache the game, refresh it in the background when online.
const CACHE = 'ultra-parry-{version}';
const CORE = ['./', 'index.html', 'manifest.webmanifest', 'icons/icon-192.png', 'icons/icon-512.png', 'icons/apple-touch-icon.png', 'peerjs.min.js', 'golden-pan-hit1.mp3', 'golden-pan-hit2.mp3', 'golden-pan-perfect.mp3'];
const FONT_CSS = {json.dumps(font_css)};
self.addEventListener('install', e => {{
  e.waitUntil(caches.open(CACHE).then(async c => {{
    await c.addAll(CORE);
    // save the fonts too, so the titles keep their look offline
    try {{
      const res = await fetch(FONT_CSS);
      await c.put(FONT_CSS, res.clone());
      const urls = [...(await res.text()).matchAll(/url\\((https:[^)]+)\\)/g)].map(m => m[1]);
      await Promise.all(urls.map(u => fetch(u).then(r => c.put(u, r))));
    }} catch (err) {{}}
  }}).then(() => self.skipWaiting()));
}});
self.addEventListener('activate', e => {{
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim()));
}});
self.addEventListener('fetch', e => {{
  if (e.request.method !== 'GET') return;
  if (e.request.mode === 'navigate') {{
    // opening the app: try for the newest version first, fall back to the saved copy offline
    e.respondWith(caches.open(CACHE).then(async cache => {{
      try {{
        const res = await Promise.race([fetch(e.request), new Promise((_, no) => setTimeout(() => no(new Error('slow')), 3000))]);
        if (res && res.ok) {{ cache.put('index.html', res.clone()); return res; }}
        throw new Error('bad response');
      }} catch (err) {{
        return (await cache.match('index.html')) || (await cache.match('./')) || Response.error();
      }}
    }}));
    return;
  }}
  e.respondWith(caches.open(CACHE).then(async cache => {{
    const hit = await cache.match(e.request, {{ ignoreVary: true }}) || await cache.match(e.request, {{ ignoreSearch: true, ignoreVary: true }});
    const net = fetch(e.request).then(res => {{
      if (res && (res.ok || res.type === 'opaque')) cache.put(e.request, res.clone());
      return res;
    }}).catch(() => hit);
    return hit || net;
  }}));
}});
'''

if DIST.exists():
    shutil.rmtree(DIST)
(DIST / 'icons').mkdir(parents=True)
(DIST / 'index.html').write_text(page)
(DIST / 'manifest.webmanifest').write_text(json.dumps(manifest, indent=2))
(DIST / 'sw.js').write_text(sw)
(DIST / '.nojekyll').write_text('')
for f in (ROOT / 'icons').glob('icon*.png'):
    shutil.copy(f, DIST / 'icons' / f.name)
shutil.copy(ROOT / 'icons' / 'apple-touch-icon.png', DIST / 'icons' / 'apple-touch-icon.png')
# online play library (PeerJS), served next to the game so no other site is needed
shutil.copy(ROOT / 'vendor' / 'peerjs.min.js', DIST / 'peerjs.min.js')
# sound effects and other files the game loads by name
for f in (ROOT / 'assets').glob('*'):
    shutil.copy(f, DIST / f.name)
print('built dist/ version', version)
