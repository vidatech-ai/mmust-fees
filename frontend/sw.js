// Minimal service worker: makes the portal installable. It never caches,
// so students always get the latest pages and live data.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", (e) => {
  if (e.request.mode === "navigate") {
    e.respondWith(fetch(e.request).catch(() =>
      new Response("You are offline. Connect to the internet and try again.",
        { headers: { "Content-Type": "text/plain" } })));
  }
});
