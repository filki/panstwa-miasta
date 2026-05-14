/*
 * Państwa-Miasta service worker.
 * Strategy:
 *  - HTML / navigations: network-first (fall back to cache, then offline shell)
 *  - Static assets (CSS/JS/icons/manifest): stale-while-revalidate
 *  - WebSocket / API: never cached
 */
const VERSION = 'pm-v12';
const STATIC_CACHE = `${VERSION}-static`;
const HTML_CACHE = `${VERSION}-html`;

const STATIC_ASSETS = [
    '/static/css/style.css',
    '/static/css/site-footer.css',
    '/static/js/audio.js',
    '/static/js/ui.js',
    '/static/js/game.js',
    '/static/js/socket.js',
    '/static/manifest.json',
    '/static/icons/icon.svg',
];

globalThis.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(STATIC_CACHE).then((cache) => cache.addAll(STATIC_ASSETS)).catch(() => {})
    );
    globalThis.skipWaiting();
});

globalThis.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(
                keys
                    .filter((k) => !k.startsWith(VERSION))
                    .map((k) => caches.delete(k))
            )
        )
    );
    globalThis.clients.claim();
});

function isStaticAsset(url) {
    return url.pathname.startsWith('/static/');
}

function isApiOrWs(url) {
    return url.pathname.startsWith('/api/') || url.pathname.startsWith('/ws/');
}

globalThis.addEventListener('fetch', (event) => {
    const req = event.request;
    if (req.method !== 'GET') return;

    const url = new URL(req.url);

    if (isApiOrWs(url)) return;

    if (req.mode === 'navigate' || req.headers.get('accept')?.includes('text/html')) {
        event.respondWith(
            fetch(req)
                .then((res) => {
                    const copy = res.clone();
                    caches.open(HTML_CACHE).then((cache) => cache.put(req, copy)).catch(() => {});
                    return res;
                })
                .catch(() => caches.match(req).then((r) => r || caches.match('/')))
        );
        return;
    }

    if (isStaticAsset(url)) {
        event.respondWith(
            caches.match(req).then((cached) => {
                const fetchPromise = fetch(req)
                    .then((res) => {
                        const copy = res.clone();
                        caches.open(STATIC_CACHE).then((cache) => cache.put(req, copy)).catch(() => {});
                        return res;
                    })
                    .catch(() => cached);
                return cached || fetchPromise;
            })
        );
    }
});
