# Skali — PRD & Working Notes

## Original problem statement
Skali — Consolidated Hardened Build Plan (Blocks 1–6). Existing app: React 18 + TS + Vite +
Capacitor (web/Android) frontend, FastAPI (Python 3.11) + MongoDB (Motor) backend, Supabase
(auth+storage), LiveKit (calls). This is a hardening/build-out of an existing production codebase
(github.com/clanchatapp-dotcom/Skali.app), deployed by the owner on Render. iOS deferred.

## Architecture (as imported into /app)
- Frontend: Vite React SPA at repo root (`src/`, `index.html`, `vite.config.ts`), built & served
  on Render as a static site. NOT an Expo app — the Emergent Expo preview does not apply.
- Backend: `backend/server.py` (single-file FastAPI, ~3.6k lines) run by supervisor as
  `uvicorn server:app` on :8001; all routes prefixed `/api`.
- DB: MongoDB (local in preview; Atlas in prod). DB name `skali`.
- Auth: Supabase JWT (asymmetric+symmetric) + local email/password (PBKDF2). Google OAuth.

## User personas
- Members (free/premium/verified), Creators (monetisation), Moderators, Co-Admins, Owner (super-admin).

## Core requirements (static, from the plan)
- Not E2E; DMs AES-256-GCM at rest, server-decryptable only for lawful/moderation with audit.
- Payments off-app (skaliapp.com); app reads entitlements. Multi-PSP account-level routing.
- Verification (Yoti/OneID) gates all monetisation; store status, never documents; fail-closed.
- Tiers Free / Premium / Verified Premium; Paid Inner Circle (£15/£30/£50). Strike ladder built.

## Implemented (this session) — Block 1: Launch-safe foundation ✅ (2026-09-24)
- **Task 1 — board tier access**: `can_read_board()` already awaits `is_admin_user_id`; verified
  stranger→followers/inner = 403, owner = 200, restricted boards hidden from listings.
- **Task 2 — CSAM hardening**: `/api/admin/csam` + escalate/resolve restricted to owner/co-admin
  (`require_full_admin`), gated by a server-side step-up secret (SHA-256 hash in
  `CSAM_STEPUP_SECRET_HASH`, raw sent as `X-Step-Up` header, never in frontend), per-admin rate
  limit (10 opens / 5 min), and immutable audit logging (added audit on CSAM list view).
- **Task 3 — DM/investigate audit**: `/api/admin/dms/{handle}` + `/api/admin/investigate/{handle}`
  now require step-up + a `legal_basis` query param (min 8 chars); basis recorded in the audit log;
  still require the subject be flagged/watchlisted.
- **Task 4 — rebrand tail**: `DB_NAME`→`skali`, bucket→`skali-media`, built-in admin emails →
  `admin@skaliapp.com`/`admin@sandbox.skali`, system profile id → `system-skali`; seed admin
  password is **env-only** (no hardcoded default; seeding skipped if unset). `render.yaml` service
  names → `skali-backend`/`skali-web`, `FRONTEND_ORIGIN`→skaliapp.com; native API fallback +
  android-apk default → `https://skali-backend.onrender.com`. **Removed committed Supabase
  service-role key + JWT secret from render.yaml → `sync:false`** (rotation required — see LEGAL.md).
- **Task 5 — legal gate**: in-app Terms / Privacy / Content / Cookie policy pages
  (`src/pages/Legal.tsx`, public route `/legal/:doc`), linked from Login footer + Settings.
  Real-world actions (Skali Ltd, ICO, trademarks, domain) tracked in `LEGAL.md`.
- Frontend wired to collect the step-up secret + legal basis at runtime (never hardcoded):
  `src/lib/api.ts` (`setStepUp`/`hasStepUp`, `X-Step-Up` header) + `src/pages/Admin.tsx` prompts.
- Verified: 22/22 backend tests pass (`backend/tests/test_block1_hardening.py`), iteration_1.json.

## Backlog (prioritised)
- **P0 (owner, non-code)**: rotate leaked Supabase service-role key + JWT secret; set prod env
  (`CSAM_STEPUP_SECRET_HASH`, `SEED_ADMIN_PASSWORD`, `DM_ENC_KEY`); ICO + Skali Ltd + trademarks.
- **P0 (next session) — Block 2**: verification spine (Yoti/OneID signed webhooks, `monetisation_enabled`
  gate, fail-closed age gate on NSFW, payout-KYC on first payout). Needs Yoti/OneID accounts.
- **P1 — Block 3**: payments + entitlements (PSP router, web checkout, money waterfall, chargebacks,
  SFW→NSFW mid-sub flip, iOS entitlement-read-only). Needs Stripe/Xsolla/CCBill.
- **P1 — Block 4**: Creator Hub (Overview/Subscribers/Shop/Finance, payouts, Printful).
- **P2 — Block 5**: discovery + tag registry + NSFW closed selector + Choices + sponsored posts.
- **P2 — Block 6**: Hive moderation, E2E (Signal), live streaming, iOS full build, appeals, PhotoDNA.

## Next tasks
1. Owner: rotate secrets + set Render env + kick off Yoti/OneID + CCBill applications (long lead).
2. Block 2 — verification spine (one block per session).
