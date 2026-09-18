# Skali.app — Restore Working App + Call/Header Fixes

## What happened
This Emergent workspace previously held a blank Expo starter template that was wired to
the user's real GitHub repo `clanchatapp-dotcom/Skali.app`. Emergent auto-commits pushed
that template to `main`, so the user's own Render deploy failed:
- backend: `emergentintegrations==0.2.0` (Emergent-private, not on public PyPI) + Python 3.14 breaking numpy/pandas
- frontend: no root `package.json` for the Vite build.

## Resolution (this session)
- The user uploaded a known-good zip of their real app (Vite + React + Capacitor
  frontend, FastAPI backend, LiveKit calls, Supabase).
- Synced that working code into `/app` (preserving platform `.git`/`.emergent` and
  protected `.env` files) so the next commit pushes the real app back onto `main`.
- Applied the two requested fixes on top of the working code and verified with a clean
  `yarn build` (Vite production build, no errors):
  1. **No audio on calls** — `src/components/CallModal.tsx`: added `RoomAudioRenderer`
     import and mounted `<RoomAudioRenderer volume={speakerOn ? 1 : 0} />` inside the
     LiveKit room. Without it, remote audio was never attached to the page (video
     rendered, nothing heard). Also makes the Speaker button actually mute/unmute.
  2. **Static chat header** — `src/pages/Messages.tsx` (~line 1225): bounded the chat
     panel to the viewport `h-[calc(100dvh-5.25rem-env(safe-area-inset-bottom))]
     md:h-screen` so the header (name + call buttons) stays fixed and only the message
     list scrolls.

## Deploy notes
- `backend/requirements.txt` is the clean list; `emergentintegrations` appears only as a
  comment, so it will not be installed by Render.
- Frontend build root has `package.json`, `vite.config.ts`, `index.html`, `render.yaml`.
- The Emergent Expo preview no longer applies (this is a Vite/Capacitor app deployed on
  the user's own Render). Final call audio/video must be verified on the deployed
  build / real device.

## Backlog
- P1: Native earpiece vs loudspeaker routing on Android (web `volume` is a stand-in).
- P2: Ringback tone for the caller while the callee's phone rings.
- P2: Missed/declined call log in the chat thread.
