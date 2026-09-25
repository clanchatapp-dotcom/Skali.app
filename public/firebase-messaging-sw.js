/* Skali — Firebase Cloud Messaging service worker */

importScripts(
  "https://www.gstatic.com/firebasejs/11.10.0/firebase-app-compat.js"
);

importScripts(
  "https://www.gstatic.com/firebasejs/11.10.0/firebase-messaging-compat.js"
);

firebase.initializeApp({
  apiKey: "AIzaSyAllxR7y4EYiIEuOHm8O-T1v6Av_-kYBdU",
  authDomain: "skaliapp-e0dee.firebaseapp.com",
  projectId: "skaliapp-e0dee",
  storageBucket: "skaliapp-e0dee.firebasestorage.app",
  messagingSenderId: "572913753788",
  appId: "1:572913753788:web:ed03e19953c82301e93ab9",
  measurementId: "G-RJ3WNHFE7E",
});

const messaging = firebase.messaging();

/*
 * Background notifications.
 *
 * If the server sends a notification payload, Firebase
 * can display it automatically. This handler is for
 * data-only messages, to avoid displaying duplicates.
 */
messaging.onBackgroundMessage((payload) => {
  const notification = payload.notification;

  if (notification) {
    return;
  }

  const data = payload.data || {};

  const title = data.title || "Skali";

  const options = {
    body: data.body || "You have a new notification.",
    icon: data.icon || "/favicon.ico",
    badge: data.badge || "/favicon.ico",
    data: {
      url: data.url || "/",
    },
  };

  return self.registration.showNotification(title, options);
});

/*
 * Open the relevant Skali page when a notification
 * is clicked.
 */
self.addEventListener("notificationclick", (event) => {
  event.notification.close();

  const targetUrl =
    event.notification.data?.url || "/";

  event.waitUntil(
    (async () => {
      const url = new URL(targetUrl, self.location.origin);

      // Never navigate notifications to another origin.
      if (url.origin !== self.location.origin) {
        return;
      }

      const windows = await self.clients.matchAll({
        type: "window",
        includeUncontrolled: true,
      });

      for (const client of windows) {
        if ("focus" in client) {
          await client.focus();

          if ("navigate" in client) {
            await client.navigate(url.href);
          }

          return;
        }
      }

      await self.clients.openWindow(url.href);
    })()
  );
});
