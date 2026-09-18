# Full-screen incoming call while the app is OUT — Skali (Android)

This drop adds an OS-native, phone-style **incoming call banner** that appears
even when the app is backgrounded, killed, or the phone is locked.

Stack used: **Capacitor 7 + FCM + LiveKit** (unchanged). We keep the existing
LiveKit ring path (`/api/call/ring`) and only change:

1. What kind of FCM message goes out on a ring.
2. Which Android service receives it — a custom one that renders a
   `CallStyle` full-screen notification instead of a plain tray notification.
3. A tiny full-screen `Activity` shown over the lock screen for the ring.

---

## 1. New Android files

Copy these **new** files into your repo at exactly these paths:

```
android/app/src/main/java/app/skali/mobile/CallMessagingService.java
android/app/src/main/java/app/skali/mobile/IncomingCallActivity.java
android/app/src/main/java/app/skali/mobile/CallActionReceiver.java
android/app/src/main/res/layout/activity_incoming_call.xml
android/app/src/main/res/drawable/ic_call_accept.xml
android/app/src/main/res/drawable/ic_call_decline.xml
android/app/src/main/res/drawable/bg_incoming_call.xml
```

## 2. Replace `AndroidManifest.xml`

Overwrite `android/app/src/main/AndroidManifest.xml` with the version in this
folder. The important additions are:

- New permissions: `USE_FULL_SCREEN_INTENT`, `WAKE_LOCK`, `VIBRATE`,
  `DISABLE_KEYGUARD`, `FOREGROUND_SERVICE`, `FOREGROUND_SERVICE_MICROPHONE`.
- Registers `.CallMessagingService` with `tools:node="replace"` so it wins the
  manifest merge against `@capacitor/push-notifications`. Ours extends
  Capacitor's service, so nothing else about push behaviour changes.
- Registers `.IncomingCallActivity` with `showWhenLocked` / `turnScreenOn` so
  the ring wakes the device.
- Adds a `skali://call?...` deep-link filter on `MainActivity` so tapping
  **Answer** routes the SPA straight into the call room.

## 3. Backend patch (`backend/server.py`)

Apply `backend/server.patch.py` from this folder:

- Add the new `push_call_ring_to_user()` helper.
- Replace the existing `POST /api/call/ring` handler with the new version.

The rest of `push_to_user` stays exactly as it is — DMs / mentions / etc.
continue to use the plain notification-style FCM path.

Why the change matters:

| Current                                        | New                                                 |
| ---------------------------------------------- | --------------------------------------------------- |
| FCM `notification=` block                      | FCM **data-only** message                           |
| Android posts a tray notification              | Our `CallMessagingService` runs and posts CallStyle |
| No wake / no lock-screen ring on killed app    | Full-screen intent + wake + lock-screen ring        |
| No accept / decline actions                    | Answer + Decline (CallStyle template on Android 12+)|

## 4. Web-side wiring (`src/lib/pushNotifications.ts`)

Overwrite `src/lib/pushNotifications.ts` with the version in this folder.

Only two additions:

- Stashes the current Supabase JWT + API base URL in SharedPreferences
  (`skali_call_prefs`) via `@capacitor/preferences`. The native
  `CallActionReceiver` reads that file to hit `/api/call/decline` while the
  app is out.
- Handles the `skali://call?...` deep link on cold start and warm resume,
  emitting a `skali:incoming-call-accept` `CustomEvent` your `App.tsx` can
  hook to open the existing `CallModal` in "answering" mode.

You'll need `@capacitor/preferences` if it isn't already installed:

```
yarn add @capacitor/preferences
```

Then re-run:

```
yarn cap:sync
```

## 5. Wire the accept event in `App.tsx` (or wherever `CallModal` lives)

Anywhere the CallModal is mounted, listen for the accept event and open the
modal in answering mode. Minimal example:

```tsx
useEffect(() => {
  const onAccept = (e: any) => {
    const { room, peer, media } = e.detail || {}
    // open your existing CallModal here, e.g.
    setIncomingCall({ room, peer, media, autoAccept: true })
  }
  window.addEventListener('skali:incoming-call-accept', onAccept)
  return () => window.removeEventListener('skali:incoming-call-accept', onAccept)
}, [])
```

Your `IncomingCallScreen.tsx` doesn't need to change — that's still the
in-app ring UI for when the app is in the foreground.

## 6. Manufacturer background restrictions (unavoidable caveat)

Xiaomi, OPPO, Huawei, Vivo (and to a lesser degree Samsung) aggressively
kill "unprotected" apps. Data-only high-priority FCM will still arrive
within seconds on stock Android and most OEM builds, but users on the
above vendors may need to grant your app **"Autostart"** and
**"No battery optimization"** permissions for the ring to fire from a
fully-killed state.

For your first internal beta this is fine; the standard way to handle it
in production is a one-time onboarding tile that deep-links the user into
those settings screens via `Intent`.

## 7. iOS

Deliberately excluded, per your 12-week plan. When you get to iOS, the
equivalent stack is:

- Register a **VoIP** APNs certificate + **PushKit** on iOS.
- On PushKit receive, use **CallKit** (`CXProvider.reportNewIncomingCall`)
  to draw Apple's own incoming-call screen.
- iOS requires reporting the call to CallKit before your process yields
  control, otherwise the OS kills the app; PushKit is the only way to do
  that from a killed state.

---

## Quick test checklist

1. `yarn cap:sync && cd android && ./gradlew installDebug` on a real device.
2. Log in on device A.
3. Force-kill the app on device A (swipe from Recents, then Settings ->
   Force stop, to be sure).
4. From device B, call the account on device A.
5. Device A should light up with a full-screen incoming-call screen with
   Answer / Decline buttons — even from the lock screen.
6. Tap **Decline** -> device B should see `call_declined` on its socket.
7. Repeat and tap **Answer** -> the app opens straight into the LiveKit
   room (via the `skali://call?...` deep link).
