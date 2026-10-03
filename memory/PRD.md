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
