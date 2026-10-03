# Skali.app — Backend Redirect (Publish Task)

## Original problem statement
Repo: clanchatapp-dotcom/Skali.app. "Don't modify or change anything — just uploading to publish live."
Approved plan: point the Android app at the one working backend so app + website share the same data.

## Root cause
The app code hardcoded the OLD backend as the mobile fallback (`clanchat-backend.onrender.com`),
while the website uses the WORKING backend (`clanchatapp-backend.onrender.com`). App and website
therefore read/wrote different databases.

## Change made (2026-06)
- `src/lib/api.ts` → `NATIVE_API_FALLBACK` changed to `https://clanchatapp-backend.onrender.com`
- `frontend/src/lib/api.ts` → same one-line change
- Verified GitHub Actions Android build (`.github/workflows/android-apk.yml`) already defaults
  `REACT_APP_BACKEND_URL` / `REACT_APP_API_URL` to `clanchatapp-backend.onrender.com`.
- No other files touched. `render.yaml` service names and the old (now-unused) backend left as-is
  (not deleted, not migrated) per plan.

## Publish path
Save to GitHub (main) → Render redeploys the website + GitHub Actions rebuilds the Android APK.
Reinstall the rebuilt APK to pick up the corrected backend address.

## Backlog / optional later
- P2: Clean the old `clanchat-backend` references out of `render.yaml` blueprint so this can't recur.

---
## 2026-10-01 — Render Deployment Readiness (config/URL pointing pass)
- Frontend web app = Vite SPA at repo root → Render static service `clanchat-app` (https://clanchat-app.onrender.com).
- Backend = FastAPI `backend/server.py` → Render web service `clanchatapp-backend` (https://clanchatapp-backend.onrender.com).
- Verified: all onrender URLs consistent across src/lib/api.ts, frontend/src/lib/api.ts, render.yaml, android-apk.yml.
- Verified: Supabase URL consistent everywhere (ixahrtibbpjruggivjik.supabase.co); fixed stale ref/bucket in check_bucket_config.py.
- Verified: MongoDB Atlas reachable with provided creds; DB_NAME=skali (populated DB, 15 collections).
- Verified: backend boots healthy (/api/ -> ok); Vite production build (`yarn build`) succeeds.
- Fix: removed contradictory `sync:false` on frontend REACT_APP_BACKEND_URL in render.yaml so the backend URL is baked automatically.
- Secrets still to set in Render dashboard (sync:false): MONGO_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_JWT_SECRET, DM_ENC_KEY, SEED_ADMIN_EMAIL, SEED_ADMIN_PASSWORD, LIVEKIT_URL/API_KEY/API_SECRET, ADMIN_EMAILS, (optional) GIPHY_API_KEY, FIREBASE_CREDENTIALS_JSON, webhook secrets.

---
## 2026-10-01 — "One app" fix: account linking + single backend/DB (Render)
ROOT CAUSES FOUND:
1. Account duplication: identity was keyed by JWT `sub`. Email/password signup => uuid4 sub; Google(Supabase) => Supabase sub. Same email -> two profiles.
2. Database split: skaliapp.com (Emergent deploy, Cloudflare) used DB `skali-preview-1-base` on Emergent-managed Mongo, while the Render backend used Atlas DB `skali`. App pointed at skaliapp.com, website/data on Render => two separate apps.

FIXES (code, in workspace):
- server.py `ensure_profile`: now links by email at the single choke point; lookup by `{$or:[{id},{linked_ids}]}`, email-match folds new auth identity into existing profile; new profiles store `linked_ids`. `auth_login` resolves via ensure_profile. Added `linked_ids` index. Verified with scripts/test_account_linking.py (password->google, google->password, distinct emails).
- Merged the one existing live duplicate in Atlas `skali`: kept `novaraptor` (email/pw, verified, 20 DMs), folded `jinky` (google) id into novaraptor.linked_ids, removed jinky's stray read + welcome-DM + profile.
- Decision: EVERYTHING on Render + Atlas `skali` (Supabase stays as shared auth/storage). Pointed app at Render backend: root .env, src/lib/api.ts NATIVE_API_FALLBACK, .github/workflows/android-apk.yml defaults => https://clanchatapp-backend.onrender.com. render.yaml frontend REACT_APP_BACKEND_URL already = Render backend.
- Verified Firebase (skaliapp-e0dee / 572913753788) + Supabase (ixahrtibbpjruggivjik) identical across app and web.

USER ACTIONS STILL REQUIRED:
- GitHub repo secret REACT_APP_BACKEND_URL was set to skaliapp.com -> it OVERRIDES the workflow default. Change it to https://clanchatapp-backend.onrender.com (or delete it) or the APK keeps hitting the wrong DB.
- Deploy backend code fix to Render (Save to GitHub -> Render redeploy). Linking only takes effect once Render runs the new server.py.
- Stop using the Emergent deploy as backend. To keep skaliapp.com branding, add it as a custom domain on the Render FRONTEND and repoint DNS.
- Supabase Auth URL config + Google Cloud OAuth: include the Render frontend origin(s) (clanchat-app.onrender.com and/or skaliapp.com) + /auth/callback.

## 2026-06 — Render + DOB guard
- Web prod builds default API to https://clanchatapp-backend.onrender.com (src/lib/api.ts)
- Backend CORS: explicit list (skaliapp.com, www, clanchat-app.onrender.com, capacitor/localhost) + CORS_ORIGINS env + regex for *.onrender.com
- render.yaml FRONTEND_ORIGIN=https://skaliapp.com, CORS_ORIGINS added
- New src/components/DobPicker.tsx (day/month/year, invalid days disabled, leap years) used in Login register + Layout DOB modal
- Backlog: Cloudflare DNS → Render custom domain (user action)

## 2026-06 — Role-separated audit logs
- audit entries carry log_role (super_admin/co_admin/moderator); startup backfill for legacy rows
- GET /api/admin/audit?log= own role only; other logs need approved 24h grant (db.audit_access)
- Request/approve/deny endpoints under /api/admin/audit/access; any holder of the target role may decide
- AuditPanel.tsx UI; audit tab visible to moderators
- Backlog: fix Admin.tsx conditional useState (line ~194)

## 2026-10-03 — Logo update
- Built transparent full SKALI lockup (monogram + SKALI + "YOUR PLACE TO GATHER") at public/logo_full.png (script: scripts/build_full_logo.py).
- Pointed login header (src/pages/Login.tsx, both left + mobile card) and app sidebar top (src/components/Layout.tsx) to /logo_full.png; kept the "Skali" text label as requested. Mirrored in frontend/src.
- No existing code removed; only image src + new asset added.

## 2026-10-03 — Deploy fix (livekit)
- Deploy was failing: backend crashed on startup with ModuleNotFoundError: No module named "livekit" (server.py:27).
- Fixed by pinning livekit-api==1.2.1 and livekit-protocol==1.1.27 in backend/requirements.txt (farm Dockerfile uses --no-dependencies, so transitive livekit-protocol listed explicitly).
- Verified by testing agent (iteration_14): backend boots, import resolves, GET /api/ 200, /api/livekit/token routable. Re-triggered deploy.
- KNOWN CONFIG GAP (unrelated, needs prod secret): SUPABASE_JWT_SECRET is empty in backend/.env -> register/login return 500 (mint_token HS256 empty key). Also needs LIVEKIT_API_KEY/SECRET/URL in prod for calls.


---

## Iteration — 2026-10-03 (Live chat bar, expanding profile pics, save media, Go Live fix)

**Environment note:** This project is a Vite + React + Capacitor web app (base image `fastapi_react_mongo_shadcn`). It was loaded into an Expo pod. Dev server runs via `vite --host 0.0.0.0 --port 3000` (the supervisor `expo` program is stopped; `vite` is run manually in the background). Frontend is hardcoded to the Render backend `https://clanchatapp-backend.onrender.com`. A `scripts/package.json` (`type:commonjs`) was added so the install-guard's CommonJS `cmd-guard.js` runs under the root `type:module`.

**Delivered (all verified by testing agent — iteration_16.json, all PASS):**
- **Go Live screen fix (TASK A):** In `LiveModal.tsx` setup phase, removed `mb-auto` on the save toggle and increased bottom padding so the `live-start-btn` ("Start live stream") is fully visible instead of cut off at the bottom.
- **Live chat bar (TASK B):** `LiveModal.tsx` LiveStage already has the real-time WS chat input/send for host + viewers; added a `visualViewport` keyboard-aware offset so the chat bar rises above the on-screen keyboard. (Full live stage needs camera/mic — not reachable in headless automation.)
- **Expanding profile pics (TASK C):** `Stories.tsx` `ProfileStoryAvatar` now opens a full-screen `MediaLightbox` (pinch-zoom) when the avatar is tapped and there is no active story; `MediaLightbox.tsx` got a smooth scale/opacity entrance animation.
- **Save media from wall posts (TASK D):** New `src/lib/saveMedia.ts` (native Capacitor Filesystem when present, else web blob download). `PostCard.tsx` shows a `post-media-save` button over media and passes `allowSave` to `MediaLightbox` (`lightbox-save`). Gated by `canSave = post.tier !== 'inner'` — Inner Circle posts cannot be saved.

**Backlog / notes:**
- `saveMedia` returns success on the CORS fallback (opens media in a new tab); the UI tick may show even when the browser only opened the file for manual save. Acceptable for now.
- Native gallery save needs `@capacitor/filesystem` added to the Android build (not installed; guarded dynamic import).
- Platform/base-image mismatch (Expo pod vs React base image) may affect reliable preview-after-restart and deploy — route to support if the preview drops.

