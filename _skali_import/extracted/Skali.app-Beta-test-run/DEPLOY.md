# Skali — Deploy (Web) & Build (Android APK)

## 0. Prerequisites for production
- **MongoDB Atlas** cluster (Render has no built-in Mongo) -> `MONGO_URL`.
- Supabase project (already have) — Google provider enabled + redirect URLs (see SETUP.md A/B).
- LiveKit Cloud project (already have).
- Fill env from `.env.example`. **Do not commit real `.env`.**

## 1. Web deploy (Render)
Two services (see `render.yaml` blueprint — New + "Blueprint" in Render, or create manually):

**Backend** (`clanchat-backend`, root `backend/`):
- Build: `pip install -r requirements.txt`
- Start: `uvicorn server:app --host 0.0.0.0 --port $PORT`
- Env: MONGO_URL (Atlas), SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_JWT_SECRET, SUPABASE_BUCKET, DM_ENC_KEY, LIVEKIT_*, ADMIN_EMAILS, FRONTEND_ORIGIN.

**Frontend** (`clanchat-web`, static):
- Build: `yarn install && yarn build`  → publish `dist/`
- SPA rewrite: `/*` → `/index.html`
- Env: REACT_APP_SUPABASE_URL, REACT_APP_SUPABASE_ANON_KEY, REACT_APP_GOOGLE_WEB_CLIENT_ID, **REACT_APP_API_URL = the backend service URL**.

After deploy, add the web origin to Supabase Auth URL config + Google Cloud JS origins (SETUP.md).

## 2. Android APK (Capacitor 7)
> This sandbox has no Android SDK, so the APK is built on YOUR machine (Android Studio + JDK 21).
The `android/` project is already scaffolded and the native Google plugin (`@capgo/capacitor-social-login`) is wired.

```bash
# 1) Point the app at your DEPLOYED backend (baked into the build):
#    set REACT_APP_API_URL (and the other REACT_APP_* vars) in .env

# 2) Build web + copy into the native project
yarn install
yarn build
npx cap sync android

# 3) One-time debug keystore (keep it PRIVATE, shared across all test builds)
keytool -genkey -v -keystore android/app/debug.keystore \
  -storepass android -keypass android -alias androiddebugkey \
  -keyalg RSA -keysize 2048 -validity 10000 -dname "CN=ClanChat Debug,O=ClanChat,C=GB"
keytool -list -v -keystore android/app/debug.keystore -alias androiddebugkey -storepass android | grep SHA1
# -> register this SHA-1 on the Android OAuth client in Google Cloud Console

# 4) Build the APK
cd android
./gradlew assembleDebug
# APK at: android/app/build/outputs/apk/debug/app-debug.apk  -> sideload to test
```

Open in Android Studio instead if you prefer: `npx cap open android`.

### Critical APK notes
- `REACT_APP_API_URL` MUST be set before `yarn build` or the app can't reach the backend (blank data / login loops).
- Native Google sign-in needs the **Android OAuth client** (`app.skali.mobile`) to have your keystore's **SHA-1** registered, and the **Web Client ID** passed as `REACT_APP_GOOGLE_WEB_CLIENT_ID` (already set). Debug SHA-1 from the spec: `2C:6F:93:26:B3:15:03:7D:77:6D:E4:01:DE:C4:5C:94:AD:C6:B3:7C` — if your generated keystore differs, register the new one.
- Always sign every sideloaded test build with the SAME keystore, or Google sign-in breaks until the new SHA-1 is added.
- The DM WebSocket and all API calls use `REACT_APP_API_URL` (absolute) inside the app — verified in code.

## 3. GitHub
`.gitignore` already excludes `.env*` (keeps `.env.example`), `*.keystore`, built assets, and Android generated/machine files. Safe to push.

## 4. CI: auto-build the APK (GitHub Actions)
Workflow: `.github/workflows/android-apk.yml` — runs on push to main/master (and manual "Run workflow"). It builds the web app, `cap sync`, builds the **debug APK**, and uploads it as an artifact `clanchat-debug-apk` (download from the Actions run page).

Add these under **GitHub repo → Settings → Secrets and variables → Actions**:
- `REACT_APP_API_URL` — your deployed backend URL (required, baked into the build).
- `REACT_APP_SUPABASE_ANON_KEY` — Supabase anon key.
- `ANDROID_KEYSTORE_BASE64` — base64 of your ONE shared `debug.keystore` (keeps SHA-1 stable so Google sign-in keeps working). Generate once locally:
  ```bash
  keytool -genkey -v -keystore debug.keystore -storepass android -keypass android \
    -alias androiddebugkey -keyalg RSA -keysize 2048 -validity 10000 -dname "CN=ClanChat Debug,O=ClanChat,C=GB"
  base64 -w0 debug.keystore    # copy the output into the secret (macOS: base64 -i debug.keystore | pbcopy)
  ```
- Optional overrides (else public defaults are used): `REACT_APP_SUPABASE_URL`, `REACT_APP_GOOGLE_WEB_CLIENT_ID`.

If `ANDROID_KEYSTORE_BASE64` is not set, the build still runs but uses a random keystore (Google sign-in won't work until its SHA-1 is registered) — the workflow prints a warning. Register the keystore's SHA-1 on the Android OAuth client in Google Cloud Console.
