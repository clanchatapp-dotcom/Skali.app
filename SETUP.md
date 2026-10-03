# Skali — Manual setup & Android build (handoff)

Code implements build steps 1-7 (Firebase removed; Supabase client, web + native Google sign-in, FastAPI JWT verification, Supabase Storage). You complete A-D below.

## A. Google Cloud Console -> Credentials
- Android client `app.skali.mobile`: add SHA-1 `2C:6F:93:26:B3:15:03:7D:77:6D:E4:01:DE:C4:5C:94:AD:C6:B3:7C` (and any keystore SHA-1 from step D).
- Web client: Authorized JS origins = `https://clanchatapp.onrender.com` + `http://localhost:3000`; Authorized redirect URI = `https://fkhsijjwkrwbwjjaapbb.supabase.co/auth/v1/callback`.
- Delete the duplicate Android client; rotate any publicly-posted keys.

## B. Supabase Dashboard
- Auth -> Providers -> Google: enable, paste Web Client ID (`24500940599-ps9kauvvquoh2ldh2iacsb04piui40cs.apps.googleusercontent.com`) + secret.
- Auth -> URL Configuration: Site URL `https://clanchatapp.onrender.com`; redirect allowlist `https://clanchatapp.onrender.com/auth/callback` + `http://localhost:3000/auth/callback`.

## C. Render env vars
Frontend service:
```
REACT_APP_SUPABASE_URL=https://fkhsijjwkrwbwjjaapbb.supabase.co
REACT_APP_SUPABASE_ANON_KEY=<anon public key>
REACT_APP_GOOGLE_WEB_CLIENT_ID=24500940599-ps9kauvvquoh2ldh2iacsb04piui40cs.apps.googleusercontent.com
```
Backend service (secrets):
```
SUPABASE_URL=https://fkhsijjwkrwbwjjaapbb.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<service role key>
SUPABASE_JWT_SECRET=<Settings > API > JWT secret>
FRONTEND_ORIGIN=https://clanchatapp.onrender.com
```

## D. Android keystore (never commit)
```bash
keytool -genkey -v -keystore android/app/debug.keystore \
  -storepass android -keypass android -alias androiddebugkey \
  -keyalg RSA -keysize 2048 -validity 10000 -dname "CN=ClanChat Debug,O=ClanChat,C=GB"
keytool -list -v -keystore android/app/debug.keystore -alias androiddebugkey -storepass android | grep SHA1
```
Register that SHA-1 (if different) in Google Cloud. Always sign every sideloaded build with THE ONE shared keystore, or Android sign-in breaks silently.

## Capacitor (Android wrapper)
```bash
yarn build                      # -> dist/
npx cap add android             # first time
npx cap sync                    # installs @capgo/capacitor-social-login native + copies web
# open android/ in Android Studio, build debug APK signed with the shared keystore
```
`capacitor.config.ts` already sets appId `app.skali.mobile`, webDir `dist`. Native Google sign-in code is in `src/lib/nativeGoogle.ts` (initialized at startup, called from the login button when `Capacitor.isNativePlatform()`).

## Notes
- `.gitignore` already excludes `.env*`, `*.keystore`, `debug.keystore`.
- In the sandbox, clan/message data uses MongoDB; Auth + Storage are real Supabase. On Render you can keep this or migrate messages to Supabase Postgres + Realtime.
