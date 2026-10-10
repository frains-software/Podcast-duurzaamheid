// Grondstof service worker: de app opent ook zonder netwerk en laadt razendsnel.
// De versie wordt bij elke publicatie vervangen, zodat een nieuwe build de oude cache opruimt.
const VERSION = "__BUILD__";
const SHELL = `grondstof-shell-${VERSION}`;
const DATA = "grondstof-data";
const SHELL_FILES = ["./", "index.html", "style.css", "app.js", "manifest.webmanifest", "favicon.png", "icon-192.png", "icon-512.png", "apple-touch-icon.png", "cover-600.jpg"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(SHELL).then((c) => c.addAll(SHELL_FILES)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k.startsWith("grondstof-shell-") && k !== SHELL).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== location.origin) return;
  // Audio altijd rechtstreeks (spoelen gebruikt range-verzoeken).
  if (url.pathname.includes("/audio/")) return;
  // Afleveringsgegevens: eerst het netwerk, offline uit de cache.
  if (url.pathname.endsWith(".json") || url.pathname.endsWith(".xml")) {
    event.respondWith(
      fetch(event.request)
        .then((res) => {
          const copy = res.clone();
          caches.open(DATA).then((c) => c.put(event.request, copy));
          return res;
        })
        .catch(() => caches.match(event.request))
    );
    return;
  }
  // De rest van de app: eerst de cache, op de achtergrond verversen.
  event.respondWith(
    caches.match(event.request, { ignoreSearch: true }).then((hit) => {
      const network = fetch(event.request)
        .then((res) => {
          if (res.ok) caches.open(SHELL).then((c) => c.put(event.request, res.clone()));
          return res;
        })
        .catch(() => hit);
      return hit || network;
    })
  );
});
