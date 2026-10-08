# Skali / Clanchat — PRD (import + Live Story category fix)

## Original problem statement
Beta social app (web + Android via Capacitor). Import the `Skali.app-Beta-test-run.zip`
non-destructively, then apply one targeted fix: remove the CATEGORY section from the
**Live Story** create screen (mobile), keep CATEGORY on the **Content Streaming** create
screen (web); make the backend tolerate a missing category. Do NOT redeploy to Render
without explicit approval.

## Architecture (as-is, verified during import)
- Frontend: React + Vite + Tailwind (TypeScript). Repo-root project (`index.html` -> `/src/main.tsx`).
  Render builds the web SPA AND the Android (Capacitor) wrapper from this one project.
- Backend: FastAPI (`backend/server.py`, ~6.1k lines) + `streaming.py`, `creator_analytics.py`, `live_alerts.py`.
- DB: MongoDB (Atlas in prod). Auth: Supabase/Google. Live media: LiveKit. Storage: Supabase.
- Deployed on Render: frontend `clanchat-app.onrender.com`, backend `clanchatapp-backend.onrender.com`.
- Repo also contains stale duplicate trees NOT built by Render: `frontend/`, `skali-app/`, `_workspace_backup/`.

## Workspace layout in /app (preview)
- `/app/frontend/` = authoritative repo-root web app (index.html + src + vite config). Runs via Vite on :3000.
- `/app/backend/`  = authoritative repo backend. Runs via uvicorn on :8001.
- `/app/_skali_import/` = pristine full extraction + `TREE_MAP.md` + `live_story_category_fix.patch`.
- Preview backend uses LOCAL Mongo (`test_database`) + no LiveKit/Supabase creds — deliberately OFF prod.

## Change implemented (2026-06, this session)
1. `src/components/LiveModal.tsx` (shared create screen, switched by `kind` prop):
   - CATEGORY block now rendered only when `kind !== 'story'` (so Live Story/mobile hides it; Content Streaming/web keeps it).
   - `beginHost` sends `category: undefined` for story kind (keeps sending the picked category for streams).
2. `backend/server.py` `POST /api/live/start`:
   - `category` default now `"live_story"` for story kind when missing/invalid (was always `just_chatting`).
   - Field `LiveStart.category` was already `Optional` -> removing it from the UI causes NO validation error.

## Verification
- Visual: both create screens screenshotted — Live Story has no CATEGORY (Title + Who-can-watch + Save); Content Streaming keeps CATEGORY. 
- Frontend bundle compiles; real app boots to login. Backend boots; `/api/` -> 200.
- NOT run: live end-to-end (going live) — requires prod LiveKit + Supabase creds we intentionally did not wire, to avoid touching production.

## Prod safety (Step 4)
- Repo `render.yaml` frontend still points to `https://clanchatapp-backend.onrender.com` (UNCHANGED).
- No repo `.env`/config modified. Not redeployed. Awaiting explicit deploy approval.

## Backlog / next
- P0 (on approval): apply `live_story_category_fix.patch` to GitHub repo `clanchatapp-dotcom/Skali.app` and redeploy Render.
- P1 (user-owned, deferred): rotate weak MongoDB Atlas password and update backend `MONGO_URL` secret in Render.
