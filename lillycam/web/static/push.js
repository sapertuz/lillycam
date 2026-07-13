"use strict";

// LillyCam Web Push test harness (PWA). Loaded only when PUSH_ENABLED=true.
// Flow: tap Enable -> request permission -> subscribe -> POST subscription to
// the Pi. Then close the app and tap Send Test (or curl /push/test) to confirm
// a notification arrives with the app in the background.
(function () {
  const enableBtn = document.getElementById("btn-push-enable");
  const testBtn = document.getElementById("btn-push-test");
  const statusEl = document.getElementById("push-status");
  if (!enableBtn) return;

  function setStatus(msg) {
    if (statusEl) statusEl.textContent = msg;
  }

  // Web Push hands us the VAPID key as URL-safe base64; the browser wants bytes.
  function urlBase64ToUint8Array(base64) {
    const pad = "=".repeat((4 - (base64.length % 4)) % 4);
    const b64 = (base64 + pad).replace(/-/g, "+").replace(/_/g, "/");
    const raw = atob(b64);
    return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
  }

  async function enablePush() {
    if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
      setStatus("Push unsupported (iOS: Add to Home Screen first)");
      return;
    }
    try {
      const reg = await navigator.serviceWorker.ready;
      const perm = await Notification.requestPermission();
      if (perm !== "granted") {
        setStatus("Permission " + perm);
        return;
      }
      const key = (await (await fetch("/push/vapid-public-key")).text()).trim();
      const sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(key),
      });
      const res = await fetch("/push/subscribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(sub),
      });
      setStatus(res.ok ? "Subscribed ✓ close the app, then Send Test" : "Subscribe failed");
    } catch (e) {
      setStatus("Error: " + (e && e.message ? e.message : e));
    }
  }

  async function testPush() {
    try {
      const res = await fetch("/push/test", { method: "POST" });
      const d = await res.json();
      setStatus(res.ok ? `Sent to ${d.sent} device(s)` : "Send failed");
    } catch (e) {
      setStatus("Error sending");
    }
  }

  enableBtn.addEventListener("click", enablePush);
  if (testBtn) testBtn.addEventListener("click", testPush);
})();
