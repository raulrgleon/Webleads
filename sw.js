// Service Worker para Webleads PWA
const CACHE_NAME = 'webleads-v10';
const API_CACHE_NAME = 'webleads-api-v1';

// Archivos para cache
const urlsToCache = [
  '/',
  '/index.html',
  '/manifest.json',
  '/config.js',
  'https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap',
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js'
];

// Instalación del Service Worker
self.addEventListener('install', event => {
  console.log('Service Worker: Installing...');
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('Service Worker: Caching files');
        return cache.addAll(urlsToCache);
      })
      .then(() => self.skipWaiting())
  );
});

// Activación del Service Worker
self.addEventListener('activate', event => {
  console.log('Service Worker: Activating...');
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheName !== CACHE_NAME && cacheName !== API_CACHE_NAME) {
            console.log('Service Worker: Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// Interceptar requests
self.addEventListener('fetch', event => {
  const requestUrl = new URL(event.request.url);

  if (event.request.mode === 'navigate' || requestUrl.pathname === '/' || requestUrl.pathname === '/index.html') {
    event.respondWith(networkFirst(event.request));
    return;
  }

  if (requestUrl.origin === self.location.origin && requestUrl.pathname.startsWith('/api/')) {
    event.respondWith(networkFirst(event.request));
    return;
  }

  if (requestUrl.origin !== self.location.origin) {
    event.respondWith(fetch(event.request));
    return;
  }

  event.respondWith(cacheFirst(event.request));
});

async function cacheFirst(request) {
  if (request.method !== 'GET') {
    return fetch(request);
  }
  const url = new URL(request.url);
  if (url.protocol !== 'http:' && url.protocol !== 'https:') {
    return fetch(request);
  }
  const cached = await caches.match(request);
  if (cached) {
    return cached;
  }
  try {
    const response = await fetch(request);
    if (response && response.ok) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, response.clone());
    }
    return response;
  } catch (error) {
    const fallback = await caches.match(request);
    if (fallback) {
      return fallback;
    }
    return Response.error();
  }
}

async function networkFirst(request) {
  try {
    const response = await fetch(request);
    if (response && response.ok) {
      const cache = await caches.open(API_CACHE_NAME);
      cache.put(request, response.clone());
    }
    return response;
  } catch (error) {
    const cached = await caches.match(request);
    if (cached) {
      return cached;
    }
    return new Response(JSON.stringify({
      error: 'No se pudo conectar con el servidor',
      businesses: []
    }), {
      status: 503,
      headers: { 'Content-Type': 'application/json' }
    });
  }
}

// Función para buscar negocios usando OpenStreetMap
async function searchBusinessesAPI(term, location, radius) {
  try {
    const url = new URL(`${self.location.origin}/api/search`);
    url.searchParams.append('term', term);
    url.searchParams.append('location', location);
    url.searchParams.append('radius', radius);

    console.log('Searching businesses via proxy:', url.toString());
    const response = await fetch(url);

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`HTTP ${response.status}: ${errorText}`);
    }

    const data = await response.json();
    return data.businesses || [];
  } catch (error) {
    console.error('Error searching businesses:', error);
    throw error;
  }
}

// Manejar mensajes del cliente
self.addEventListener('message', event => {
  if (event.data && event.data.type === 'SEARCH_YELP') {
    const { term, location, radius } = event.data;

    searchBusinessesAPI(term, location, radius)
      .then(businesses => {
        event.ports[0].postMessage({
          type: 'YELP_RESULTS',
          businesses: businesses
        });
      })
      .catch(error => {
        event.ports[0].postMessage({
          type: 'YELP_ERROR',
          error: error.message
        });
      });
  }

  if (event.data && event.data.action === 'skipWaiting') {
    self.skipWaiting();
  }
});
