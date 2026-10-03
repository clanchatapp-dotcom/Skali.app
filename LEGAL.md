# Skali — Launch Legal & Compliance Checklist (Block 1, Task 5)

This tracks the legal gate for a launch-safe public test. In-app policy summaries are
live at `/legal/{terms,privacy,content,cookies}` (see `src/pages/Legal.tsx`), linked from
the sign-in screen and Settings → "Legal & policies".

## In-app (done in code)
- [x] Terms of Service (in-app summary)
- [x] Privacy Policy (in-app summary)
- [x] Content & Community Policy (in-app summary)
- [x] Cookie Policy (in-app summary)
- [x] Policies linked from Login footer + Settings

## Real-world actions (owner to complete — NOT code)
- [ ] Publish full policies on skaliapp.com and keep the in-app summaries in sync.
- [ ] Register **Skali Ltd** (UK limited company).
- [ ] Register as a data controller with the **ICO** (Information Commissioner's Office).
- [ ] Re-scope / file **trademarks** under "Skali" (retire "ClanChat" marks).
- [ ] Confirm the canonical domain: **skaliapp.com** (site) with **skali.app** redirecting to it.
- [ ] Update contact addresses used in policies: `legal@skaliapp.com`, `privacy@skaliapp.com`.
- [ ] Data Processing Agreements with processors (Supabase, Render, Yoti/OneID, PSPs, Firebase).

## Rebrand tail (done in code)
- [x] `DB_NAME` default → `skali`; `SUPABASE_BUCKET` default → `skali-media`.
- [x] Built-in admin emails → `admin@skaliapp.com`, `admin@sandbox.skali` (kept owner's personal email).
- [x] System profile id → `system-skali`.
- [x] Seed admin password: **no hardcoded default** — env-only (`SEED_ADMIN_PASSWORD`); seeding is skipped if unset.
- [x] `render.yaml` service names → `skali-backend` / `skali-web`; `FRONTEND_ORIGIN` → `https://skaliapp.com`.
- [x] Native API fallback + android-apk default → `https://skali-backend.onrender.com`.

## ⚠️ Secret rotation required (was committed to the repo)
`render.yaml` previously committed the **Supabase service-role key** and **JWT secret** in
plaintext. They are now `sync:false` (set in the Render dashboard), but because they were in
git history you MUST rotate them:
- [ ] Rotate the Supabase **service_role** key and **JWT secret** in the Supabase dashboard.
- [ ] Set new values in Render (`SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`).
- [ ] Set `CSAM_STEPUP_SECRET_HASH`, `SEED_ADMIN_EMAIL`, `SEED_ADMIN_PASSWORD`, `DM_ENC_KEY` in Render.

### Generate a production step-up secret
```
python3 -c "import secrets,hashlib; s=secrets.token_urlsafe(24); print('SECRET (share out-of-band):',s); print('CSAM_STEPUP_SECRET_HASH:',hashlib.sha256(s.encode()).hexdigest())"
```
Give the raw SECRET to the owner + co-admins only; put the HASH in Render.

## ⚠️ Deployment note on the rebrand
Renaming the Render services in `render.yaml` (`clanchat-*` → `skali-*`) creates NEW services
if you re-apply the blueprint. To avoid orphaning your live backend, either rename the existing
services in the Render dashboard, or keep `REACT_APP_API_URL` pointing at your current backend URL.
