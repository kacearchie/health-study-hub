// static/sw.js - Service Worker for Offline Support

const CACHE_NAME = 'health-hub-v1.0';
const OFFLINE_URL = '/offline';

// Assets to cache for offline use
const ASSETS_TO_CACHE = [
    '/',
    '/offline',
    '/manifest.json',
    '/api/notes',
    '/api/quizzes',
    '/api/stats'
];

// Install event - Cache assets
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => {
                console.log('[Service Worker] Caching assets...');
                return cache.addAll(ASSETS_TO_CACHE);
            })
            .then(() => self.skipWaiting())
    );
});

// Activate event - Clean old caches
self.addEventListener('activate', event => {
    const cacheWhitelist = [CACHE_NAME];
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.map(cacheName => {
                    if (cacheWhitelist.indexOf(cacheName) === -1) {
                        console.log('[Service Worker] Deleting old cache:', cacheName);
                        return caches.delete(cacheName);
                    }
                })
            );
        })
        .then(() => self.clients.claim())
    );
});

// Fetch event - Serve from cache or network
self.addEventListener('fetch', event => {
    const request = event.request;
    const url = new URL(request.url);

    // Skip cross-origin requests
    if (url.origin !== location.origin) {
        return;
    }

    // Handle API requests - try network first, then cache
    if (url.pathname.startsWith('/api/')) {
        event.respondWith(
            fetch(request)
                .then(response => {
                    // Cache the response for offline use
                    const responseClone = response.clone();
                    caches.open(CACHE_NAME).then(cache => {
                        cache.put(request, responseClone);
                    });
                    return response;
                })
                .catch(() => {
                    // If offline, try cache
                    return caches.match(request);
                })
        );
        return;
    }

    // Handle HTML pages
    if (request.mode === 'navigate' || url.pathname === '/') {
        event.respondWith(
            fetch(request)
                .then(response => {
                    // Cache the page
                    const responseClone = response.clone();
                    caches.open(CACHE_NAME).then(cache => {
                        cache.put(request, responseClone);
                    });
                    return response;
                })
                .catch(() => {
                    // If offline, show offline page
                    return caches.match(OFFLINE_URL);
                })
        );
        return;
    }

    // Handle static assets - cache first, then network
    event.respondWith(
        caches.match(request)
            .then(response => {
                if (response) {
                    return response;
                }
                return fetch(request)
                    .then(response => {
                        // Cache the response
                        const responseClone = response.clone();
                        caches.open(CACHE_NAME).then(cache => {
                            cache.put(request, responseClone);
                        });
                        return response;
                    });
            })
    );
});

// Background sync for offline data
self.addEventListener('sync', event => {
    if (event.tag === 'sync-data') {
        event.waitUntil(syncData());
    }
});

async function syncData() {
    try {
        const cache = await caches.open(CACHE_NAME);
        const requests = await cache.match('/offline-queue');
        if (requests) {
            // Process offline queue
            const data = await requests.json();
            await fetch('/api/offline/sync', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            // Clear the queue after sync
            await cache.delete('/offline-queue');
        }
    } catch (error) {
        console.error('[Service Worker] Sync failed:', error);
    }
}

// Push notification support
self.addEventListener('push', event => {
    const data = event.data.json();
    const options = {
        body: data.body || 'Time to study! 📚',
        icon: '/static/icons/icon-192x192.png',
        badge: '/static/icons/icon-72x72.png',
        vibrate: [200, 100, 200],
        actions: [
            { action: 'open', title: 'Open App' },
            { action: 'dismiss', title: 'Dismiss' }
        ]
    };
    event.waitUntil(
        self.registration.showNotification(data.title || 'Health Study Hub', options)
    );
});

self.addEventListener('notificationclick', event => {
    event.notification.close();
    if (event.action === 'open') {
        event.waitUntil(
            clients.openWindow('/')
        );
    }
});