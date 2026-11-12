// WanderFolk service worker: makes the app installable and opens it fast.
// Trip data (/api) always comes from the network, so nobody sees stale votes or plans.
const CACHE = "wanderfolk-v2";
const SHELL = ["/", "/trip/", "/manifest.webmanifest", "/icon.svg", "/scene.svg"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin || url.pathname.startsWith("/api")) return;
  // Pages: network first, so a new version shows up right away; the cached shell is the offline fallback.
  if (e.request.mode === "navigate") {
    e.respondWith(
      fetch(e.request)
        .then((res) => { const copy = res.clone(); caches.open(CACHE).then((c) => c.put(url.pathname, copy)); return res; })
        .catch(() => caches.match(url.pathname).then((hit) => hit || caches.match("/"))),
    );
    return;
  }
  // Built assets have hashed names, so a cached copy is always the right one.
  e.respondWith(
    caches.match(e.request).then((hit) => hit || fetch(e.request).then((res) => {
      if (res.ok) { const copy = res.clone(); caches.open(CACHE).then((c) => c.put(e.request, copy)); }
      return res;
    })),
  );
});
