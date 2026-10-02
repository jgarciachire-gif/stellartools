const CACHE_NAME = 'stellartools-shell-v1';

self.addEventListener('install', event => {
    self.skipWaiting();
});

self.addEventListener('activate', event => {
    event.waitUntil(
        self.clients.claim()
    );
});