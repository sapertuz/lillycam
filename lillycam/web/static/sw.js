// LillyCam service worker.
// Served from "/sw.js" (root scope) so it controls the whole app. Its only
// jobs are to exist (so the PWA is installable) and to show Web Push alerts.
// No offline caching: LillyCam is useless without the live Pi anyway.

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));

self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (e) {
    data = { body: event.data ? event.data.text() : "" };
  }
  const title = data.title || "LillyCam";
  const options = {
    body: data.body || "",
    icon: "/static/icon-192.png",
    badge: "/static/icon-192.png",
    tag: data.tag || "lillycam",
    data: { url: data.url || "/" },
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || "/";
  event.waitUntil(
    self.clients
      .matchAll({ type: "window", includeUncontrolled: true })
      .then((windows) => {
        for (const client of windows) {
          if ("focus" in client) return client.focus();
        }
        if (self.clients.openWindow) return self.clients.openWindow(url);
      })
  );
});
