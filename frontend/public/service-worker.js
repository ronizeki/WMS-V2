/* eslint-disable no-restricted-globals */
/*
 * StockPilot WMS service worker.
 *
 * Strategy (safe, multi-tenant aware):
 *  - App shell navigations: network-first, falling back to the cached shell so the
 *    application UI still loads offline.
 *  - Static same-origin assets: stale-while-revalidate.
 *  - API traffic (/api/** and the configured backend origin): network-only. Tenant
 *    data is never written to the shared browser cache, so signing out or switching
 *    organizations can never surface another tenant's records. Stock changes require
 *    a live connection; the app surfaces an offline banner and a clear error instead.
 */

const VERSION = 'v1';
const SHELL_CACHE = `stockpilot-shell-${VERSION}`;
const ASSET_CACHE = `stockpilot-assets-${VERSION}`;
const SHELL_URL = '/index.html';

const PRECACHE = ['/', '/index.html', '/manifest.json', '/logo.svg'];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(SHELL_CACHE)
      .then((cache) => cache.addAll(PRECACHE.map((url) => new Request(url, { cache: 'reload' }))))
      .catch(() => undefined)
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  const keep = new Set([SHELL_CACHE, ASSET_CACHE]);
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => !keep.has(key)).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') self.skipWaiting();
});

function isApiRequest(url) {
  if (url.pathname.startsWith('/api/')) return true;
  const backend = self.STOCKPILOT_BACKEND_URL;
  return Boolean(backend) && url.href.startsWith(backend);
}

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return; // never intercept mutations

  const url = new URL(request.url);

  // API: always go to the network. No caching of tenant data.
  if (isApiRequest(url)) return;

  // Navigations: network-first with app-shell fallback.
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((response) => {
          const copy = response.clone();
          caches.open(SHELL_CACHE).then((cache) => cache.put(SHELL_URL, copy)).catch(() => undefined);
          return response;
        })
        .catch(() => caches.match(SHELL_URL).then((cached) => cached || Response.error()))
    );
    return;
  }

  // Same-origin static assets: stale-while-revalidate.
  if (url.origin === self.location.origin) {
    event.respondWith(
      caches.match(request).then((cached) => {
        const network = fetch(request)
          .then((response) => {
            if (response && response.status === 200 && response.type === 'basic') {
              const copy = response.clone();
              caches.open(ASSET_CACHE).then((cache) => cache.put(request, copy)).catch(() => undefined);
            }
            return response;
          })
          .catch(() => cached);
        return cached || network;
      })
    );
  }
});
