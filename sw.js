// Service worker for the worship sheet reader.
// Strategy: precache app shell, network-first for HTML so updates roll out
// fast, cache-first for static assets. Image data is cached separately
// in IndexedDB by the app code (keyed by Dropbox file rev).

const VERSION = '1.4.0';
const APP_CACHE = 'worship-app-' + VERSION;
const SHELL = ['./', './index.html', './manifest.json'];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(APP_CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (e) => {
  e.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter(k => k !== APP_CACHE).map(k => caches.delete(k)));
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  // Never touch the Dropbox API — auth headers and POST bodies must go straight through.
  if (url.hostname.endsWith('dropboxapi.com') || url.hostname.endsWith('dropbox.com')) return;
  // Only handle our own origin.
  if (url.origin !== self.location.origin) return;

  if (e.request.mode === 'navigate' || url.pathname.endsWith('.html') || url.pathname === '/') {
    // Network-first for HTML so updates ship quickly; fall back to cache offline.
    e.respondWith((async () => {
      try {
        const fresh = await fetch(e.request);
        const c = await caches.open(APP_CACHE);
        c.put(e.request, fresh.clone());
        return fresh;
      } catch (err) {
        const cached = await caches.match(e.request) || await caches.match('./index.html');
        if (cached) return cached;
        throw err;
      }
    })());
    return;
  }

  // Cache-first for everything else (JS/CSS/icons/manifest)
  e.respondWith((async () => {
    const cached = await caches.match(e.request);
    if (cached) return cached;
    try {
      const fresh = await fetch(e.request);
      if (fresh.ok) {
        const c = await caches.open(APP_CACHE);
        c.put(e.request, fresh.clone());
      }
      return fresh;
    } catch (err) {
      if (cached) return cached;
      throw err;
    }
  })());
});
