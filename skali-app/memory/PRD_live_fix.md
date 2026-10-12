# Skali — Live Stream Fixes (June 2026)

## Problem statement (verbatim)
- When someone goes live, messages from others are NOT appearing on the host's screen.
- For the person going live, remove the chat bar. It should just be MUTE MIC, TURN CAM OFF, TURN CAM AROUND and END LIVE.
- Constraint: DO NOT DELETE OR MOVE CODE. JUST EDIT.

## Codebase note
- Active/deployed source = repo-root `src/` (index.html -> /src/main.tsx; render.yaml frontend service + capacitor both `vite build` from repo root).
- `frontend/` is a stale duplicate (not built by Render/Android). Edited anyway to stay consistent.

## Changes (src/components/LiveModal.tsx + frontend/src mirror)
1. Live chat side-channel WebSocket now auto-reconnects (exponential backoff, cap 5s).
   Root cause of "others' messages not appearing": the plain WS (chat/hearts/viewers) is
   separate from LiveKit and dropped silently on mobile background / network flips, so the
   host stopped receiving chat while video (LiveKit, self-reconnecting) kept working.
2. Host (live broadcaster) bottom bar restructured: ONLY Mute Mic / Turn Cam Off /
   Turn Cam Around / End Live. Chat input + heart removed for the host.
   Incoming messages show as the existing bottom-left overlay.
   Viewers keep chat input (+ heart, + wave in the frontend/ copy).

## Verification
- `yarn build` (root) passes.
- Full live E2E (two real participants over LiveKit) cannot be simulated in this environment.

## Backlog / next
- Optional: show a live "who's talking" audio indicator on active speakers.

## APK build fix (June 2026)
Error: `checkDebugAarMetadata` failed — `androidx.browser:browser:1.9.0`
(pulled by @capgo/capacitor-social-login) requires compileSdk 36 + AGP 8.9.1,
but the CI build used android-35 + AGP 8.7.2.

Root cause: the built branch had no committed `android/`, so CI's
`npx cap add android` generated a DEFAULT Capacitor project (SDK 35 / AGP 8.7.2).
That also caused the "no debug keystore found" signing warning.

Fix:
1. Committed `android/` into the workspace with compileSdkVersion = 36,
   AGP 8.9.1, and the stable `android/app/debug.keystore`.
2. Added a CI safety-net step in .github/workflows/android-apk.yml (after
   `cap sync`) that pins compileSdkVersion=36 and AGP 8.9.1 via sed, so the
   build is correct even if `cap add android` regenerates defaults.

Verified locally: web `yarn build` passes; sed pins produce 36/8.9.1 for both
the committed config and a default cap-add config. A full APK build needs the
GitHub Action re-run (no Android SDK/JDK in this environment).

## Round 3 (June 2026) — viewer can't message/like on APK + profile photo/story
Reported: on the installed Android app, a viewer tapping Send/heart does NOTHING
(not even their own echo). Also tapping a profile avatar to enlarge photo / view
story stopped working.

Root cause (chat/like): the live chat/hearts rode a separate plain WebSocket
(/api/ws/live) that does NOT connect inside the Android WebView, while LiveKit
(the video) DOES connect. Backend WS proven working via 2-user probe, so the
failure was the WebView WS transport, not the server.

Fix (src/components/LiveModal.tsx):
- Chat + hearts now travel over the LiveKit DATA CHANNEL (useDataChannel topic
  'skali-live'), with an optimistic local echo on send (LiveKit doesn't loop a
  sender's own data back). Sender name derived from LiveKit participant .name.
- WS kept only for viewer-count/system/join/end; chat+heart removed from WS
  send AND receive to avoid duplicates.
- Viewer count now derived from LiveKit remote participants (reliable on APK),
  max() with the WS figure.
- NOTE: frontend/ duplicate LiveModal left as-is (dead code; not built by Render
  or Capacitor which both build repo root).

Fix (src/components/Stories.tsx ProfileStoryAvatar):
- Tapping a profile avatar: has story + photo -> chooser (View story / View
  profile photo); story only -> view story; photo only -> enlarge via
  MediaLightbox; neither -> inert. Photo-enlarge path was entirely missing.

VERIFIED: minted 2 LiveKit tokens for the user's real cloud
(clanchat-rlnieg0m.livekit.cloud); in a headless browser connected 2
participants; viewer published chat+heart on topic 'skali-live' and the host
received BOTH (gotChat=true, gotHeart=true, from '#janedoe'). yarn build passes.
Full in-app UI E2E not run here (app is Supabase-auth gated; no Supabase in preview).
