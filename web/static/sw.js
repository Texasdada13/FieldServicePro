const CACHE_NAME = 'fsp-mobile-v1';
const SHELL_URLS = [
  '/mobile/',
  '/static/css/mobile.css',
  '/static/js/mobile.js',
  '/static/manifest.json',
  '/static/icon-192.png'
];

// Install: cache the shell
self.addEventListener('install', function(event) {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(function(cache) { return cache.addAll(SHELL_URLS); })
      .then(function() { return self.skipWaiting(); })
  );
});

// Activate: remove old caches
self.addEventListener('activate', function(event) {
  event.waitUntil(
    caches.keys().then(function(keys) {
      return Promise.all(keys.filter(function(k) { return k !== CACHE_NAME; }).map(function(k) { return caches.delete(k); }));
    }).then(function() { return self.clients.claim(); })
  );
});

// Fetch: cache-first for shell, network-first for pages
self.addEventListener('fetch', function(event) {
  var url = new URL(event.request.url);

  // Never cache POST or API
  if (event.request.method !== 'GET') return;
  if (url.pathname.startsWith('/mobile/api/')) return;

  // Shell assets: cache-first
  if (SHELL_URLS.indexOf(url.pathname) !== -1) {
    event.respondWith(
      caches.match(event.request).then(function(r) { return r || fetch(event.request); })
    );
    return;
  }

  // Mobile pages: network-first with cache fallback
  if (url.pathname.startsWith('/mobile/')) {
    event.respondWith(
      fetch(event.request)
        .then(function(response) {
          var clone = response.clone();
          caches.open(CACHE_NAME).then(function(cache) { cache.put(event.request, clone); });
          return response;
        })
        .catch(function() { return caches.match(event.request); })
    );
  }
});
