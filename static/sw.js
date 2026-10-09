// Cache only the public shell. Private API responses and prospect data never enter CacheStorage.
const CACHE='webleads-dnet-v2';const FILES=['/static/style.css','/static/app.js','/favicon.svg'];
self.addEventListener('install',e=>{e.waitUntil(caches.open(CACHE).then(c=>c.addAll(FILES)).then(()=>self.skipWaiting()))});
self.addEventListener('activate',e=>{e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim()))});
self.addEventListener('fetch',e=>{if(e.request.method!=='GET'||!FILES.includes(new URL(e.request.url).pathname))return;e.respondWith(fetch(e.request).catch(()=>caches.match(e.request)))});
