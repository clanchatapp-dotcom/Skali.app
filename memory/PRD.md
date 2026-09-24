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

## Implemented (session 2) — Block 2 + Block 3 ✅ (2026-09-24)
### Block 2 — Verification spine
- Profile gains `verification: {identity:{status,provider,at}, age:{status,provider,region,at}}`
  and a computed `monetisation_enabled`. Status only — no ID documents are ever persisted.
- `POST /api/verification/start` (identity|age × yoti|oneid) marks status `pending` + returns a
  provider redirect URL (stub). `GET /api/verification/status` reports state + gate.
- Signed webhooks `POST /api/webhooks/yoti` + `/api/webhooks/oneid`: HMAC-SHA256 over raw body
  (`X-Yoti-Signature` / `X-OneID-Signature`); unsigned/invalid → 401 (fail-closed). Write status only.
- `monetisation_ok` gate = identity verified AND age-verified adult → exposed in `/me`; `require_monetisation`
  dependency guards creator endpoints. Fail-closed NSFW feed gate now also requires age-verified adult.
- Hardcoded minor block stays on top: a minor age-`verified` webhook is forced to `failed`.
### Block 3 — Payments + entitlements
- Collections: `entitlements`, `transactions` (ledger), `subscriptions`, `checkout_sessions`,
  `payout_balances`, `reconsent_prompts`.
- Account-level PSP router (`route_psp`): NSFW account → CCBill (fallback Segpay/Paxum), else Stripe.
- Money waterfall (`compute_waterfall`): VAT carved first (VAT-inclusive prices); Skali fee on NET ex-VAT
  (10% subs/inner-circle, 7.5% tips); PSP fee borne by creator; Premium = 100% Skali. Skali positive-margin verified.
- `POST /api/checkout/session` (web, skaliapp.com) → PSP + quote + hosted URL; app only READS
  `GET /api/entitlements`. Signed PSP webhooks `/api/webhooks/{stripe,ccbill,xsolla}` grant/revoke +
  write ledger; chargeback → proportional creator clawback + repeat-offender flag (≥3).
- SFW→NSFW flip (`POST /api/account/nsfw-flip`): existing Stripe/Xsolla subs run to period end → cancel →
  re-subscribe on CCBill; fan re-consent prompts created; future routing = CCBill. Adult money never on Stripe retroactively.
- `GET /api/creator/finance` — consolidated cross-PSP ledger (gross/VAT/PSP fee/Skali cut/creator net) — Block 4 foundation.
- Frontend: `src/pages/Verify.tsx` (route `/verify`, linked from Settings) drives identity+age verification and
  shows the monetisation locked/unlocked banner; `api.ts` gains verificationStatus/Start, entitlements, creatorFinance.
- Verified: 27/27 local + 15/15 independent testing-agent tests pass (iteration_2.json).


- **P0 (owner, non-code)**: rotate leaked Supabase service-role key + JWT secret; set prod env
  (`CSAM_STEPUP_SECRET_HASH`, `SEED_ADMIN_PASSWORD`, `DM_ENC_KEY`); ICO + Skali Ltd + trademarks.
- **P0 (next session) — Block 2**: verification spine (Yoti/OneID signed webhooks, `monetisation_enabled`
  gate, fail-closed age gate on NSFW, payout-KYC on first payout). Needs Yoti/OneID accounts.
- **P1 — Block 3**: payments + entitlements (PSP router, web checkout, money waterfall, chargebacks,
  SFW→NSFW mid-sub flip, iOS entitlement-read-only). Needs Stripe/Xsolla/CCBill.
- **P1 — Block 4**: Creator Hub (Overview/Subscribers/Shop/Finance, payouts, Printful).
- **P2 — Block 5**: discovery + tag registry + NSFW closed selector + Choices + sponsored posts.
- **P2 — Block 6**: Hive moderation, E2E (Signal), live streaming, iOS full build, appeals, PhotoDNA.

## Implemented (session 3) — Block 4 Creator Hub + Verified badges ✅ (2026-09-24)
- **Creator Hub** (`src/pages/CreatorHub.tsx`, route `/creator`, linked from Settings; gated by `monetisation_enabled`):
  Overview (`/api/creator/overview`), Subscribers (`/api/creator/subscribers`), Shop (digital + Printful physical:
  `/api/creator/shop`, `/api/creator/shop/products`, `/api/shop/order/{id}`), Finance (totals, CSV export
  `/api/creator/finance/export.csv`, monthly tax statements issued by Skali `/api/creator/finance/tax-docs`),
  Payouts (`/api/creator/payout-settings`, `/api/creator/payouts`, `/api/creator/payouts/request` — KYC on first payout).
  Every endpoint requires verification. Creator Health DEFERRED.
- **Verified badges (blue tick)**: serializers expose `verified` = identity-checked; `AccountBadge` renders a blue
  BadgeCheck on feed authors, profiles, wall, DM info. Staff/tier badges to be reworked later.
- Verified: 20/20 local + 14/14 independent tests (iteration_3.json). Vite production build passes.


## Implemented (session 4) — Block 5 Discovery + subscribe/tip + storefront ✅ (2026-09-24)
- **Tag registry** (`tags` collection): normalise (lowercase/de-leet/singularise) + dedupe; per-tier cap on `POST /api/posts`
  (Free 3 / Premium 6 / Verified 9 via `TIER_LIMITS.tags`); `GET /api/tags/similar` ("similar tags exist") + `/api/tags/trending`.
- **Closed NSFW selector** (`@NSFW/@GNSFW/@LNSFW/@TNSFW`, server-extensible via `config.nsfw_vocab`, `POST /api/admin/nsfw-tags`):
  `nsfw_tags` on posts are chosen from the vocab, adults-only (fail-closed); explicit freeform tags blocked; `GET /api/nsfw-tags`
  returns empty for ineligible users. NSFW post → `nsfw:true` + flips `account_nsfw` (→CCBill routing).
- **Hate/abuse**: banned/explicit tag attempts return a generic warning (word hidden) + silent `abuse_log`; ≥3 attempts → auto-watchlist (no auto-strike).
- **Choices** (`/choices` page + `GET /api/choices`, `POST /api/choices/opt-in`): opt-in, tag-driven discovery, separate from the feed;
  the ONLY place labelled sponsored posts appear. **Sponsored** (`POST /api/sponsored`, verified-only, topic-targeted, no NSFW to ineligible).
- **Subscribe/Tip**: Profile shows Subscribe (Inner Circle tiers) + Tip buttons → `POST /api/checkout/session` → off-app checkout URL.
  Creator offers configurable (`PUT /api/creator/offers`, `GET /api/creators/{h}/offers`).
- **Creator storefront**: public Shop tab on Profile (`GET /api/creators/{h}/shop`) → Buy → `POST /api/shop/order/{id}`.
- **Verified badge** field added to serializers (blue tick). New nav item "Choices" (Compass).
- Verified: 18/18 local + 15/15 independent tests (iteration_4.json). Vite production build passes.


## Next tasks
1. Owner: rotate secrets + set Render env + kick off Yoti/OneID + CCBill applications (long lead).
2. Block 2 — verification spine (one block per session).
