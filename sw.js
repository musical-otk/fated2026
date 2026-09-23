const CACHE_NAME = 'fated2026-v4';
const BASE = '/fated2026';

const PRECACHE_URLS = [
  BASE + '/',
  BASE + '/index.html',
  BASE + '/manifest.json',
  BASE + '/icon-192.png',
  BASE + '/apple-touch-icon.png',
  BASE + '/icon-512.png',
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(PRECACHE_URLS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// 모든 리소스 네트워크 우선 — 오프라인 시만 캐시 폴백
self.addEventListener('fetch', event => {
  event.respondWith(
    fetch(event.request)
      .then(response => {
        if (response && response.status === 200) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
        }
        return response;
      })
      // 딥링크(?date=...)로 들어오면 주소가 달라 캐시에 없다.
      // 오프라인일 때 화면이 아예 안 뜨므로 화면 이동은 앱 첫 페이지로 되돌린다.
      .catch(() => caches.match(event.request).then(hit =>
        hit || (event.request.mode === 'navigate' ? caches.match(BASE + '/') : undefined)))
  );
});
