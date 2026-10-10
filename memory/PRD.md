# Skali — PRD / Working Memory

## [2026-10-08] Support claim + profile followers fix — tested 100% (iteration_31)
- POST /api/admin/support/claim/{handle} {claim} stores support_status.assigned = {id, handle, display_name, at}. Threads and thread detail return `assigned`. The list shows "Handled by you/#handle"; the modal has Claim / Take over (with a confirm) / Release. All of these go to the audit log.
- Bug fix: the Followers/Following stat blocks on your own profile now open /connections?tab=followers|following. They're disabled on other people's profiles because the counts are owner-only.

## [2026-10-08] Support: Mark as solved
- POST /api/admin/support/solve/{handle} {solved} (require_support) stores the status in db.support_status and marks the member's messages read. A newer message from the member reopens the chat automatically (_support_solved).
- Threads are sorted Unread → Open → Solved, with a "Solved by #handle" label. The thread modal has a Mark solved / Reopen button. Both actions are written to the audit log.

## [2026-10-08] Support inbox + Feed streaming banner — tested 100% (iteration_30)
- The support inbox is shared by all staff (super_admin/co_admin/moderator) AND the Skali Team login (require_support). Unread conversations are listed first, with Unread/Earlier headings, an unread badge on the Support tab (GET /api/admin/support/unread) and a refresh every 20s.
- Skali Team login (is_support_bot): /admin shows only the Support inbox, Settings has a "Support inbox" link, and there's no DOB gate or onboarding.
- Feed: LiveNowBanner in the pinned header uses GET /api/live/alerted-now, which returns content streams from creators the viewer gets alerts for. Tapping it opens the stream, "See all" goes to Find → Streamers, and dismissing hides it for the session.
- Preview seed: fake OBS stream doc 'preview-fake-stream' in the local live_streams collection, plus a local bot auth record.

## [2026-10-08] Streamer Alerts + live DB cleanup — tested 100% (iteration_29)
- Streamer Alerts already existed (followers/Inner Circle notified by default, with per-creator opt-out). Gap fixed: non-followers can now opt in. live_alerts.alert_enabled() defaults to follower status; _notify_live adds opted-in subscribers for public streams. The Find → Streamers rows have an "Alert me" / "Alerts on" bell (AlertBell in FindStreamers.tsx).
- PRODUCTION Atlas DB (skali): removed 12 test/bot accounts and all their data. Kept: thisismajortom, sunweskongstudios, novaraptor, mileygallacher, clanchatadmin, skali_support.
- The support bot (skali-support-bot, #skali_support) can now sign in with skaliappteam@gmail.com through the email form. Verified against the live Render backend.

## [2026-10-08] Import (Test-run zip) + UI Rearrangement — tested 100% (iteration_28)
### Problem statement
"Open this and bring it to this workspace DO NOT DELETE OR MOVE ANYTHING" + approved plan (UI rearrangement).
### Import
- Zip copied untouched to /app/skali-app (reference original, never edited).
- Previous workspace files backed up to /app/_workspace_backup before the zip contents were copied into /app (preview copy).
- Preview-only backend/.env: SUPABASE_JWT_SECRET + DM_ENC_KEY (random local values) so email login works. Supabase/LiveKit/Firebase keys NOT set in preview.
### Done (preview copy, /app/src + /app/backend)
- Feed: inline composer removed; composer is a sheet opened from centre + (Create post / Live Story chooser). Header+tabs+StoryRail pinned (ResizeObserver padding).
- Bottom nav: Feed · Find · + · Messages · Me (Activity removed, also from desktop sidebar).
- Messages: Activity pill (unread count from /api/unread `activity`; GET /api/activity marks read). Activity page has back button.
- Find: Discover shows results only while typing (# people, @ interests). New Streamers tab (FindStreamers.tsx, GET /api/streamers?q=).
- Settings → Preferences: Comfort Zone | Interests sub-tabs (InterestsManager.tsx).
- Me: "Skali presents" removed; FitName auto-shrinks handle 22→13px, underline full width. Creator Studio "Live" → "Content Streaming".
- Live Story vs Content Streaming: /api/live/start `kind` ('story' open to all, 'stream' gated by can_go_live); _live_out returns kind. Story rail shows Live Story rings; "Watch Streams" circle → Find → Streamers. Live page titled Content Streaming, lists only streams.
- AvatarMenu.tsx: View profile / View story (story only if active) on post authors, Messages list and DM header.
### Backlog
- P1: Hand back code (GitHub / download / Render redeploy) — Phase 3.
- P2: Further rearrangements after user review.


## [2026-10-07] Live alerts + 24h replays (tested 100%, iteration_26)
- NEW backend/live_alerts.py: GET/PUT /api/live-alerts/{handle} (per fan+creator, default ON), GET /api/live/replays (?handle=).
- _notify_live skips fans with alerts off; push url → /watch/{id} (OBS) or /live?watch={id} (camera). Push tap now navigates in-SPA.
- Frontend: Profile LiveAlertToggle (followers / Inner Circle), LiveAlertBanner on user-websocket live_started, Live page ReplaysSection,
  /live?watch= opens viewer, StreamWatch replay "Nh left" label.

## [2026-10-07] Promo expiry + mobile viewing
- Promo codes accept `expires_on` (YYYY-MM-DD); auto-switch off after that day (lazy expire on list + checkout check), shown as "expired".
- Streaming is website-only: Go Live hidden in the native (Capacitor) app; Live page shows a website-only note for allowed users.
- Stories rail: "Watch Live" shortcut (→ /live) for anyone who can't go live, so viewers on mobile reach live discovery.
- Viewer chat already present (StreamWatch chat panel below video on mobile; LiveModal overlay/sidebar). Mod actions now visible on touch.

## [2026-10-07] Analytics v2 + Go-Live gating (tested 100%, iteration_25)
- Go Live limited to moderator / co_admin / super_admin + owner-granted users (`profiles.can_stream`). Gate in /api/live/start and
  /api/stream/ingress|ingress/reset|start. Owner-only /api/admin/streamers (+assign/remove), UI in Admin > Roles (StreamersPanel).
  /api/me `can_go_live`; Live page / Stories / Creator Studio hide Go Live for others (watching unchanged).
- Analytics: range picker (month | 3m | all) on all tabs + exports; promo codes CRUD (creator_promos) applied at Inner Circle checkout
  (promo_code), uses counted on fulfilment; gentle milestones (subscribers/renewals) with dismiss; real watch time via
  POST /api/watch/{live_id}/heartbeat (watch_sessions, Inner Circle viewers only, 30s pings, 45s cap).
- Preview test accounts: owner@ (super_admin) and mod@ (moderator) set via Mongo role.

## [2026-10-07] Beta Test 2 — Import + Creator Studio Analytics (tested 100%, iteration_24)
### Problem statement
"DO NOT DELETE OR MOVE CODE. WE'RE JUST EDITING/ADDING. OPEN THIS ZIP AND BRING THE CODE IN HERE"
+ approved plan: Analytics button in Creator Studio (Me) for creators; non-creators see only Add to Story.
### Done
- Zip imported as-is into /app (all files/folders; platform `.emergent/` left untouched). Root deps installed (yarn), backend deps installed.
- Local preview only: added SUPABASE_JWT_SECRET to backend/.env so email login works in preview.
- NEW backend/creator_analytics.py (mounted at end of server.py, isolated try/except): GET /api/creator/analytics,
  /api/creator/analytics/export.csv, /export.pdf. Real data from transactions/subscriptions/entitlements/shop_orders/payouts/dms;
  untracked metrics return `sample: [...]` flags. Creator Health hide switch reuses PUT /api/creator/health/settings {hidden}.
- server.py public_profile: added `creator_account` (is_creator | creator_override | monetisation_ok).
- Frontend (root /app/src): NEW pages/CreatorAnalytics.tsx (/creator/analytics, full screen, 5 tabs, swipe, Sample tags, CSV/PDF export);
  Profile.tsx Creator Studio: Live + new Analytics shown only when creator_account; api.ts methods; App.tsx route.
### Backlog
- P1: Real tracking for avg watch time, promos/discounts, Printful inventory sync; real Skali fee rates tuning.
- P2: Date-range filters, deeper charts, renewal-drop alerts.

## [2026-10-07] Current job — UX/Flow Makeover + Live Streaming (FINAL / LOCKED)
### Original problem statement (customer's words, abridged headings kept)
"Relocate and consolidate navigation (both apps), then add OBS streaming with Twitch-style chat and
time-limited VODs on web. Existing files, logic, auth, and features stay intact — edit and move only, never delete."
Phase 1: (1) Feed tabs General | Following | Interests (reuse Interests logic). (2) Bottom nav remove
"Choices" → Find sub-tab. (3) Bottom nav remove "Live" → Me/Profile → Creator Studio next to "Add Story".
(4) Fewer items, re-centered. (5) Remove duplicate Shop tab from Media/Wall/Boards/Audio row; Shop reachable
via My Links → Shop. Mobile Story-style go live stays as-is.
Phase 2 (web only, isolated): OBS RTMP via LiveKit Ingress (per-creator URL+key, create/reset, live status);
Twitch-style ephemeral chat over LiveKit data channels, auth-gated, mods restricted to Inner Circle
(delete msg / timeout); VODs recorded per session, downloadable by streamer, auto-deleted after 24h (scheduled job).
### User choices
- RTMP only (v1). One persistent stream key per creator + manual Reset. VODs in existing Supabase bucket.
- Ship Phase 1 first, pause for sign-off before Phase 2.
### Architecture finding
- No React Native `mobile/` folder exists: mobile = Capacitor Android wrapper of the same ROOT `/app/src`
  Vite build. So Phase 1 edits apply to web + mobile at once. `/app/frontend/src` is a stale copy (not edited).
- Local git repo at /app on branch `beta-test`: baseline commit = uploaded zip, then Phase 1 commit.
### Phase 1 implemented (2026-10-07) — tested 100% (iteration_21)
- Layout.tsx: Live + Choices removed from NAV (bottom nav + desktop sidebar) → 5 evenly spaced items.
- Feed.tsx: segmented General | Following | Interests; Interests uses existing `/api/interests/feed`.
- Search.tsx (Find): tabs Discover | Choices (embeds Choices.tsx with `embedded` prop; `/search?tab=choices`).
  Interest Feed tab moved out of Find into Feed → Interests. `/choices` and `/live` routes kept.
- Profile.tsx: "Creator Studio" block = Add to Story + Live (→ /live). SHOP removed from tab row; ShopTab exported.
- Links.tsx: "Shop · Coming soon" placeholder replaced by real Shop section (ShopTab).
### 2026-10-07 — Desktop composer fix + Phase 2 implemented — tested 100% (iteration_22, 14/14 pytest)
- Feed.tsx: dropped `md:pt-4` so desktop composer sits below the absolute header.
- NEW backend/streaming.py (mounted at end of server.py inside try/except → isolated):
  /api/stream/ingress (GET/POST), /ingress/reset (409 while live), /start (requires OBS publishing),
  /end, /mods (Inner Circle only), /vods, /vods/{id}/download (host only, signed URL valid to expiry),
  /{live_id} (info + VOD playback), /{live_id}/join (LiveKit token w/ profile metadata, data-only),
  /{live_id}/chat/delete, /{live_id}/timeout (server send_data + update_participant).
  Collections: stream_ingress, stream_vods, stream_mods, stream_timeouts; OBS sessions live in
  live_streams with source='obs', room obs-{uid}. Maintenance loop (60s): delete VODs past 24h
  (Supabase object delete), finalize egress, auto-end OBS sessions after 3 min no signal, lift timeouts.
- VOD egress = RoomComposite MP4 → Supabase S3 (env: SUPABASE_S3_REGION, SUPABASE_S3_ENDPOINT,
  SUPABASE_S3_ACCESS_KEY_ID, SUPABASE_S3_SECRET_ACCESS_KEY; fallback session-token mode w/ SUPABASE_ANON_KEY).
- NEW frontend: components/stream/{ObsStudioPanel,StreamMods,StreamVods,StreamChat,CopyField,StreamBoundary}.tsx,
  pages/StreamWatch.tsx (/watch/:liveId, outside Layout). Live.tsx shows OBS panel on web only (not native);
  Live.tsx + Stories.tsx route OBS streams to /watch.
- Verified live with real LiveKit (ffmpeg RTMP push): ingress, go live, 2-user chat, mod delete, end.
### Next
- P0: Add Supabase S3 keys on Render, then verify a real VOD record → download → 24h deletion.
- P1: Verify chat timeout in UI with a real stream (API path tested; UI timeout not explicitly re-run).

## Original problem statement
Existing "Skali" app (React Vite+TS + FastAPI + MongoDB; LiveKit + Supabase + Firebase already
integrated). User asked to **rework the live-streaming feature into a Twitch-style service** — an
improved layout, NOT a rebuild of Skali. Keep existing colours. "DO NOT MOVE OR DELETE FILES."

## User choices
- Tier-based audiences: **Tier 1 = Public** (Twitch-style open discovery), plus **Followers-only**,
  **Inner-Circle-only**, and **Group-DM** streaming.
- Categories: Gaming, Just Chatting, Music, Creative, IRL, Sports.
- Credentials provided for LiveKit + Supabase (in /app/backend/.env). Firebase optional.

## CRITICAL: which frontend tree ships
The real build tree is the **repo ROOT `/app/src`** — used by Render (`yarn build`, see render.yaml)
and the Android APK (`cap:sync` = `vite build && cap sync android`). Entry: `/app/index.html` →
`/src/main.tsx`. The `/app/frontend` folder is a **stale CRA-era copy** that is NOT shipped. The
Emergent preview also serves the root app (supervisor runs `yarn start` in `/app/frontend` →
`"cd .. && yarn start"` → root `vite --host 0.0.0.0 --port 3000`). All feature code lives in `/app/src`.

## What's implemented (this session)
### Backend (`/app/backend/server.py`, live section — shared by all builds)
- `LIVE_AUDIENCES = {public, followers, inner, group}`, `LIVE_CATEGORIES` (6).
- `LiveStart` gains `audience`, `category`, `group_id`. `_can_watch_live()` public→anyone,
  group→members, inner/followers as before. `_live_out()` adds category + current viewer count.
  `_notify_live()` handles group + public.
- Endpoints: `/api/live/start` (stores category/group, 403 if not group member), `/api/live/categories`,
  `/api/live?category=`, `/api/live/past/{handle}`, `/api/live/{id}/join` (+category), `/api/live/{id}/end`.
- Verified 19/19 pytest (`backend/tests/test_live_streaming_tiered.py`).

### Frontend — in ROOT `/app/src`
- NEW `src/lib/liveCategories.ts`, NEW `src/pages/Live.tsx` (Twitch discovery: Go Live CTA,
  category chips w/ counts, "Live Now" grid, past-streams list).
- `src/components/LiveModal.tsx` reworked: Go Live setup (title + category grid +
  Public/Followers/Inner/Group + group picker + save); responsive viewer — desktop Stream-chat
  sidebar, mobile overlay. **Chat/hearts still ride the LiveKit data channel** (Android-WebView fix preserved).
- `src/lib/api.ts` (live methods), `src/components/Layout.tsx` (Live nav tab), `src/App.tsx` (/live route).

### Build/preview
- Root `vite.config.ts` unchanged (no hardcoded URL). `vite build` (APK/Render) ignores local `.env`
  → bakes Render backend (original behaviour). Preview uses same-origin `/api` → local backend.
  `yarn build` verified compiling. Testing agent: 100% backend + frontend.

## Earlier misstep (fixed)
First pass wrongly edited the stale `/app/frontend/src` and changed its `start` script, which would
have broken APK builds. Fixed: reverted start script, removed stray `frontend/.env`, restored the full
repo (android/ + all root files), re-implemented the feature in canonical `/app/src`, verified build + tests.

## Backlog / next
- Real VOD recording of past streams (LiveKit Egress + storage) — currently metadata + optional
  host-side "save to wall".
- Profile "Live" tab (mockup #4) + profile-while-live banner (mockup #7). Creator Studio analytics (#6).
- Stream thumbnails/preview frames on discovery cards.
- Minor: dedicated 400 for missing group_id; rate-limit /api/live/start.
